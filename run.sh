#!/bin/sh

# Install uv if it is missing; otherwise check for a newer version.
if ! command -v uv >/dev/null 2>&1; then
    echo "Installing UV..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    PATH="$HOME/.local/bin:$PATH"
    export PATH
    if ! command -v uv >/dev/null 2>&1; then
        echo "uv installation failed." >&2
        exit 1
    fi
elif ! uv self update; then
    echo "Could not update uv; continuing with the installed version." >&2
fi

# Check for compatible GPU.
echo "Determining correct configuration for your GPU..."
torch_variant=`uv run --no-sync src/setup/probeGPU.py`
if [ "$torch_variant" = "" ]; then 
    torch_variant="cpu"
fi;
if [ "$torch_variant" = "cpu" ]; then 
    echo "Setup did not find a compatible GPU. Setup will continue with CPU-only dependencies. You can re-run after installing drivers to enable GPU support."
fi;

# Sync with final GPU configuration
uv sync --extra $torch_variant

# Run
echo "Starting StarTrails AI..."
uv run --no-sync src/main.py
