#!/bin/bash

# Shared Unix setup for repository launches and prepared macOS releases.
set -euo pipefail

packaged=false
launch=false
repair=false
project_path=
while (($#)); do
    case "$1" in
        --packaged) packaged=true ;;
        --launch) launch=true ;;
        --repair) repair=true ;;
        --) shift; if (($#)); then project_path=$1; shift; fi; break ;;
        -*) printf 'Unknown setup option: %s\n' "$1" >&2; exit 2 ;;
        *) if [[ -n $project_path ]]; then printf 'Only one project path is supported.\n' >&2; exit 2; fi
           project_path=$1 ;;
    esac
    shift
done
if (($#)); then printf 'Only one project path is supported.\n' >&2; exit 2; fi
if [[ -n $project_path && $project_path != /* ]]; then
    project_path="$(pwd -P)/$project_path"
fi

application_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd -P)
cd "$application_dir"

if $packaged; then
    # release.conf is generated from the build's pinned toolchain metadata.
    source "$application_dir/release.conf"
    runtime_dir="$application_dir/runtime"
    environment_dir="$runtime_dir/venv"
    ready_file="$runtime_dir/ready.txt"
    uv="$application_dir/tools/uv"
    python="$environment_dir/bin/python"
    export UV_PROJECT_ENVIRONMENT="$environment_dir"
    export UV_PYTHON_INSTALL_DIR="$runtime_dir/python"
    export UV_CACHE_DIR="$HOME/Library/Caches/StarTrails/uv"
    export UV_PYTHON_PREFERENCE=only-managed
    export UV_PYTHON_INSTALL_BIN=0
    if [[ ${STARTRAILS_WORK_DIR+x} != x ]]; then
        export STARTRAILS_WORK_DIR="$HOME/Documents/Startrails"
    fi

    lock_hash=$(shasum -a 256 uv.lock | awk '{print $1}')
    expected_ready="$release_id $lock_hash"
    ready=false
    if ! $repair && [[ -x $python && -f $ready_file ]] &&
        [[ $(head -n 1 "$ready_file") == "$expected_ready" ]]; then
        ready=true
    fi
    if ! $ready && $launch && ! $repair; then
        printf 'The installed environment needs repair. Run the StarTrails AI installer again.\n' >&2
        exit 1
    fi
else
    ready=false
    if ! command -v uv >/dev/null 2>&1; then
        printf 'Installing uv...\n'
        curl -LsSf https://astral.sh/uv/install.sh | sh
        export PATH="$HOME/.local/bin:$PATH"
    else
        uv self update || printf 'Could not update uv; continuing with the installed version.\n' >&2
    fi
    uv=$(command -v uv)
    if [[ -z $uv ]]; then printf 'uv installation failed.\n' >&2; exit 1; fi
fi

prepare_environment() {
    if $packaged && [[ ! -x $uv || $("$uv" --version) != "uv $uv_version "* ]]; then
        printf 'Bundled uv is missing or does not match this release. Reinstall StarTrails AI.\n' >&2
        return 1
    fi
    printf 'Preparing Python and checking GPU support...\n'
    if $packaged; then
        run_args=(run --no-project --python "$python_version" --)
    else
        run_args=(run --no-sync --)
    fi
    torch_variant=$("$uv" "${run_args[@]}" src/setup/probeGPU.py)
    "$uv" "${run_args[@]}" src/setup/check_setup.py --variant "$torch_variant"
    printf 'Using torch variant: %s\n' "$torch_variant"
    sync_args=(sync --extra "$torch_variant")
    if $packaged; then sync_args+=(--locked --python "$python_version"); fi
    "$uv" "${sync_args[@]}"
    check_args=(run --no-sync)
    if $packaged; then check_args+=(--python "$python_version"); fi
    check_args+=(-- src/setup/check_runtime.py --variant "$torch_variant")
    if $packaged; then check_args+=(--notice-file "$runtime_dir/prerequisites.txt"); fi
    "$uv" "${check_args[@]}"
    if $packaged; then
        if [[ ! -x $python ]]; then
            printf 'The Python environment is incomplete. Run repair.\n' >&2
            exit 1
        fi
        printf '%s\n%s\n' "$expected_ready" "$torch_variant" >"$ready_file.tmp"
        mv -f "$ready_file.tmp" "$ready_file"
    fi
    printf 'Python and dependencies are ready.\n'
}

if ! $ready; then
    if $packaged; then
        mkdir -p "$runtime_dir" "$UV_CACHE_DIR"
        setup_lock="$runtime_dir/.setup-lock"
        if ! mkdir "$setup_lock" 2>/dev/null; then
            printf 'Another setup is running. If it stopped unexpectedly, remove %s and run repair.\n' "$setup_lock" >&2
            exit 1
        fi
        trap 'rmdir "$setup_lock"' EXIT
        rm -f "$ready_file"
        prepare_environment 2>&1 | tee "$runtime_dir/setup.log"
    else
        prepare_environment
    fi
fi

if $launch; then
    printf 'Starting StarTrails AI...\n'
    if $packaged; then
        if [[ -n $project_path ]]; then exec "$python" src/main.py "$project_path"; fi
        exec "$python" src/main.py
    fi
    if [[ -n $project_path ]]; then exec "$uv" run --no-sync -- src/main.py "$project_path"; fi
    exec "$uv" run --no-sync -- src/main.py
fi
