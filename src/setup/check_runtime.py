"""Check native dependencies before declaring an environment ready to launch."""

import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variant", required=True)
    parser.add_argument("--notice-file", type=Path, help="Write prerequisite guidance for the installer to display.")
    args = parser.parse_args()
    # These imports exercise native dependencies before a packaged install is ready.
    import cv2
    import openvino
    from PySide6 import QtWidgets
    import torch
    import torchvision

    print(
        f"Loaded Qt {QtWidgets.__name__}, OpenCV {cv2.__version__}, OpenVINO {openvino.__version__}, "
        f"PyTorch {torch.__version__}, torchvision {torchvision.__version__}."
    )
    notice = ""
    if args.variant.startswith("cu"):
        try:
            import cupy as cp

            # A kernel also checks the toolkit compiler components needed by CuPy.
            cp.arange(1, dtype=cp.float32).sum().get()
        except Exception as error:
            notice = (
                "NVIDIA stacking acceleration is unavailable. Install a compatible NVIDIA driver "
                f"and CUDA Toolkit {torch.version.cuda}, then run Repair StarTrails AI. "
                "CPU stacking remains available."
            )
            print(f"{notice} Details: {error}", file=sys.stderr)
    elif args.variant == "mps":
        if torch.backends.mps.is_available():
            torch.ones(1, device="mps").sum().item()
        else:
            notice = "Apple GPU acceleration is unavailable. CPU processing remains available."
            print(notice, file=sys.stderr)

    # Smoke-test the bundled GraXpert PyTorch model when present.
    from setup.check_finish_models import check_graxpert
    from startrails.lib.model_manifest import GRAXPERT_MANIFEST
    from startrails.paths import APPLICATION_DIR
    import numpy as np

    model_path = APPLICATION_DIR / "models" / GRAXPERT_MANIFEST.relative_path
    if not model_path.is_file():
        message = "GraXpert model is missing. Install the model archive and run repair to enable Finish denoising."
        print(message, file=sys.stderr)
        notice = "\n".join(filter(None, (notice, message)))
        if args.notice_file is not None:
            args.notice_file.write_text(notice, encoding="utf-8")
        return  # Other modes and neutral finishing remain usable.
    sample = np.full((256, 256, 3), 0.5, dtype=np.float32)
    report = check_graxpert(model_path, sample)
    print(f"GraXpert runtime: {report['execution_device']} (configured: {report['configured_device']})")
    if report["fallback_reason"]:
        gpu_msg = f"GraXpert GPU execution fell back to CPU: {report['fallback_reason']}"
        print(gpu_msg, file=sys.stderr)
        notice = "\n".join(filter(None, (notice, gpu_msg)))

    if args.notice_file is not None:
        args.notice_file.write_text(notice, encoding="utf-8")


if __name__ == "__main__":
    main()
