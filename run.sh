#!/bin/sh

# Install UV if not already installed
uv_version=`uv -V`
if [ "$uv_version" = "" ]; then 
    echo "Installing UV..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
fi;

# Check for CUDA GPU. (Also prompts initial packages sync)
echo "Determining correct configuration for your GPU..."
torch_variant=`uv run src/setup/probeGPU.py`
if [ "$torch_variant" = "" ]; then 
    torch_variant="cpu"
fi;
if [ "$torch_variant" = "cpu" ]; then 
    echo "Install did not find a CUDA compatible GPU. Install will continue with CPU-only dependencies. You can re-run install.bat after installing drivers or CUDA Toolkit to enable GPU support."
fi;

# Sync with final GPU configuration
uv sync --extra $torch_variant

# Run
echo "Starting StarStack AI..."
uv run src/main.py