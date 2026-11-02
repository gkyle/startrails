"""StarNet2 CLI probe, execution contract, progress streaming, and process boundary."""

from concurrent.futures import CancelledError
from dataclasses import dataclass
import json
import os
from queue import Empty, Queue
import signal
import subprocess
import sys
from threading import Thread
from typing import Any, Callable, Dict, List, Optional, Tuple

from startrails.lib.finish.defaults import DEFAULT_STARNET_STRIDE


DEFAULT_STRIDE = DEFAULT_STARNET_STRIDE
MIN_STRIDE = 2
MAX_STRIDE = 512
PROCESS_POLL_SECONDS = 0.1
PROCESS_TERMINATE_TIMEOUT_SECONDS = 2.0


class StarNetError(Exception):
    """Raised when StarNet CLI execution fails."""


@dataclass(frozen=True)
class StarNetProbeInfo:
    """Introspection results from StarNet2 CLI (--machine-info)."""

    executable: str
    version: str
    build: str
    backend_id: str
    backend_name: str
    highlight_protection_supported: bool
    highlight_protection_default: bool
    linear_mtf_supported: bool
    options: List[str]
    raw_info: Dict[str, Any]


def parse_starnet_machine_info(json_text: str) -> StarNetProbeInfo:
    """Parse output from starnet2 --machine-info into typed StarNetProbeInfo."""
    try:
        data = json.loads(json_text)
    except json.JSONDecodeError as exc:
        raise StarNetError(f"Failed to parse StarNet --machine-info JSON: {exc}") from exc

    if not isinstance(data, dict):
        raise StarNetError(f"Expected JSON object from StarNet --machine-info, got {type(data).__name__}")

    version = str(data.get("version", ""))
    build = str(data.get("build", ""))
    backend = data.get("backend", {})
    if not isinstance(backend, dict):
        raise StarNetError("StarNet --machine-info backend must be an object")
    backend_id = str(backend.get("id", ""))
    backend_name = str(backend.get("display_name", ""))
    features = data.get("features", {})
    if not isinstance(features, dict):
        raise StarNetError("StarNet --machine-info features must be an object")
    hp = features.get("highlight_protection", {})
    linear = features.get("linear_mtf", {})
    if not isinstance(hp, dict) or not isinstance(linear, dict):
        raise StarNetError("StarNet --machine-info feature descriptions must be objects")
    raw_options = data.get("options", [])
    if not isinstance(raw_options, list) or any(not isinstance(opt, dict) for opt in raw_options):
        raise StarNetError("StarNet --machine-info options must be an array of objects")
    options = [opt.get("name", "") for opt in raw_options]
    if any(not isinstance(name, str) for name in options):
        raise StarNetError("StarNet --machine-info option names must be strings")

    return StarNetProbeInfo(
        executable=str(data.get("executable", "starnet2")),
        version=version,
        build=build,
        backend_id=backend_id,
        backend_name=backend_name,
        highlight_protection_supported=bool(hp.get("supported", False)),
        highlight_protection_default=bool(hp.get("default", True)),
        linear_mtf_supported=bool(linear.get("supported", False)),
        options=options,
        raw_info=data,
    )


def build_starnet_cli_args(
    executable_path: str,
    input_path: str,
    output_path: str,
    mask_path: Optional[str] = None,
    unscreen_path: Optional[str] = None,
    stride: int = DEFAULT_STRIDE,
    disable_highlights: bool = False,
    upsample: bool = False,
    machine_progress: bool = True,
    quiet: bool = False,
) -> List[str]:
    """Build the argument list for invoking StarNet2 CLI.

    Args:
        executable_path: Path to the starnet2 executable.
        input_path: Path to input image (16-bit TIFF recommended).
        output_path: Path to output starless image.
        mask_path: Optional path for star mask output.
        unscreen_path: Optional path for unscreen star layer.
        stride: Stride window (even integer between 2 and 512).
        disable_highlights: If True, passes -d to disable highlight protection.
        upsample: If True, passes -u for intermediate 2x upsampling.
        machine_progress: If True, passes --machine-progress.
        quiet: If True, passes -q.

    Returns:
        List of command line argument strings.
    """
    if type(stride) is not int or stride < MIN_STRIDE or stride > MAX_STRIDE or stride % 2 != 0:
        raise ValueError(f"Stride must be an even integer between {MIN_STRIDE} and {MAX_STRIDE}, got {stride}")

    args = [executable_path, "-i", str(input_path), "-o", str(output_path), "-s", str(stride)]
    if mask_path:
        args.extend(["-m", str(mask_path)])
    if unscreen_path:
        args.extend(["-n", str(unscreen_path)])
    if disable_highlights:
        args.append("-d")
    if upsample:
        args.append("-u")
    if machine_progress:
        args.append("--machine-progress")
    if quiet:
        args.append("-q")

    return args


def parse_starnet_progress_line(line: str) -> Optional[Dict[str, Any]]:
    """Parse a single JSON Line from StarNet's --machine-progress stderr output."""
    clean = line.strip()
    if not clean.startswith("{") or not clean.endswith("}"):
        return None
    try:
        return json.loads(clean)
    except json.JSONDecodeError:
        return None


def run_starnet_process(
    cmd: List[str],
    cwd: Optional[str] = None,
    should_interrupt: Optional[Callable[[], bool]] = None,
    progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    process_runner: Optional[Callable[..., Any]] = None,
) -> Tuple[int, str, str]:
    """Execute StarNet CLI process with cancellation monitoring and progress streaming.

    Args:
        cmd: Command argument list.
        cwd: Working directory for the process.
        should_interrupt: Callable returning True if process should be aborted.
        progress_callback: Callback receiving parsed progress/diagnostic JSON dicts.
        process_runner: Factory for launching process (defaults to subprocess.Popen).

    Returns:
        Tuple of (returncode, stdout_str, stderr_str).

    Raises:
        CancelledError: If interrupted before or during execution.
        StarNetError: If process exits with non-zero status.
    """
    if should_interrupt and should_interrupt():
        raise CancelledError("StarNet execution cancelled before start")

    runner = process_runner or subprocess.Popen
    popen_kwargs: Dict[str, Any] = {
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "text": True,
        "bufsize": 1,
    }
    if cwd:
        popen_kwargs["cwd"] = cwd

    # Start an isolated process session on POSIX.
    if not sys.platform.startswith("win"):
        popen_kwargs["start_new_session"] = True

    try:
        proc = runner(cmd, **popen_kwargs)
    except OSError as exc:
        raise StarNetError(f"Cannot start StarNet: {exc}") from exc

    # Each pipe has its own reader: a silent stderr must not block cancellation
    # or prevent stdout from being drained. Callbacks stay on the caller thread.
    messages = Queue()
    readers = []
    outputs = {"stdout": [], "stderr": []}

    def read_stream(name, stream):
        try:
            for line in stream:
                messages.put((name, line))
        except Exception as exc:
            messages.put((name, exc))
        finally:
            messages.put((name, None))

    try:
        for name in outputs:
            reader = Thread(target=read_stream, args=(name, getattr(proc, name)), name=f"starnet-{name}")
            reader.start()
            readers.append(reader)

        open_streams = len(readers)
        while open_streams or proc.poll() is None:
            if should_interrupt and should_interrupt():
                raise CancelledError("StarNet execution cancelled by user")
            try:
                name, message = messages.get(timeout=PROCESS_POLL_SECONDS)
            except Empty:
                continue
            if message is None:
                open_streams -= 1
            elif isinstance(message, Exception):
                raise StarNetError(f"Cannot read StarNet {name}: {message}") from message
            else:
                outputs[name].append(message)
                if name == "stderr" and progress_callback is not None:
                    event = parse_starnet_progress_line(message)
                    if event is not None:
                        progress_callback(event)
        proc.wait()
    except BaseException:
        # Kill the isolated POSIX group as well as the helper, including any
        # descendant that inherited its pipes. Always reap after kill escalation.
        _stop_starnet_process(proc)
        raise
    finally:
        for reader in readers:
            reader.join()
        proc.stdout.close()
        proc.stderr.close()

    stdout_str = "".join(outputs["stdout"])
    stderr_str = "".join(outputs["stderr"])
    if proc.returncode != 0:
        raise StarNetError(
            f"StarNet process exited with code {proc.returncode}.\nStderr: {stderr_str}\nStdout: {stdout_str}"
        )
    return proc.returncode, stdout_str, stderr_str


def _stop_starnet_process(proc) -> None:
    def send_signal(force):
        try:
            if sys.platform != "win32":
                os.killpg(proc.pid, signal.SIGKILL if force else signal.SIGTERM)
            elif proc.poll() is None:
                proc.kill() if force else proc.terminate()
        except ProcessLookupError:
            pass  # The process/group already exited between poll and signal.

    send_signal(force=False)
    try:
        proc.wait(timeout=PROCESS_TERMINATE_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        send_signal(force=True)
        proc.wait()
    # Descendants can outlive the group leader and still hold its pipes open.
    if sys.platform != "win32":
        send_signal(force=True)
