import subprocess
import re
import sys
import platform

def get_cuda_version():
    try:
        result = subprocess.run(['nvidia-smi'], capture_output=True, text=True, check=True)
        output = result.stdout
        cuda_version_match = re.search(r'CUDA(?:\s+UMD)?\s*Version:\s*([\d.]+)', output)
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

def has_apple_silicon():
    """Select macOS dependencies; check functional MPS after installation."""
    if sys.platform != 'darwin':
        return False
    
    # Check if running on Apple Silicon (arm64)
    if platform.machine() != 'arm64':
        return False
    
    return True
    
if __name__ == "__main__":
    # First check for MPS on macOS
    if has_apple_silicon():
        print("mps", end="")
    else:
        # Check for CUDA
        cuda_version = get_cuda_version()
        if cuda_version is not None:
            try:
                major = int(cuda_version.split(".")[0])
                if major == 13:
                    print("cu133", end="")
                elif major == 12:
                    print("cu124", end="")
                elif major == 11:
                    print("cu118", end="")
                else:
                    print("cpu", end="")
            except (ValueError, IndexError):
                print("cpu", end="")
        else:
            print("cpu", end="")
