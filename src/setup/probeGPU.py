import subprocess
import re
import sys
import platform

def get_cuda_version():
    try:
        result = subprocess.run(['nvidia-smi'], capture_output=True, text=True, check=True)
        output = result.stdout
        cuda_version_match = re.search(r' CUDA Version: \s*([\d.]+)', output)
        if cuda_version_match:
            return cuda_version_match.group(1)
        else:
            print("CUDA version not found. Is CUDA Toolkit installed?", file=sys.stderr)
            return None
    except subprocess.CalledProcessError as e:
        print(f"Error executing nvidia-smi: {e}", file=sys.stderr)
        return None
    except FileNotFoundError:
        print("nvidia-smi command not found. Is the NVIDIA driver installed?", file=sys.stderr)
        return None

def has_mps_support():
    """Check if Apple Silicon MPS is available."""
    if sys.platform != 'darwin':
        return False
    
    # Check if running on Apple Silicon (arm64)
    if platform.machine() != 'arm64':
        return False
    
    # Verify macOS version supports MPS (macOS 12.3+)
    try:
        mac_version = platform.mac_ver()[0]
        if mac_version:
            major, minor = map(int, mac_version.split('.')[:2])
            # MPS requires macOS 12.3 or later
            if major > 12 or (major == 12 and minor >= 3):
                return True
    except (ValueError, AttributeError):
        pass
    
    return False
    
if __name__ == "__main__":
    # First check for MPS on macOS
    if has_mps_support():
        print("mps", end="")
    else:
        # Check for CUDA
        cuda_version = get_cuda_version()
        if not cuda_version is None:
            cuda_version = int(float(cuda_version))
            if cuda_version == 12:
                print("cu124",end="")
            elif cuda_version == 11:
                print("cu118",end="")
            else:
                print("cpu",end="")
        else:
            print("cpu",end="")

