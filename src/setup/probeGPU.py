import subprocess
import re

def get_cuda_version():
    try:
        result = subprocess.run(['nvidia-smi'], capture_output=True, text=True, check=True)
        output = result.stdout
        cuda_version_match = re.search(r' CUDA Version: \s*([\d.]+)', output)
        if cuda_version_match:
            return cuda_version_match.group(1)
        else:
            print("CUDA version not found. Is CUDA Toolkit installed?")
            return None
    except subprocess.CalledProcessError as e:
        print(f"Error executing nvidia-smi: {e}")
        return None
    except FileNotFoundError:
        print("nvidia-smi command not found. Is the NVIDIA driver installed?")
        return None
    
if __name__ == "__main__":
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

