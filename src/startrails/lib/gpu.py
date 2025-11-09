import torch
import pynvml
import psutil
from typing import List, Tuple

class GPUInfo:

    def __init__(self):
        try:
            self.cudaAvailable = torch.cuda.is_available()
        except Exception as e:
            self.cudaAvailable = False

        try:
            self.mpsAvailable = torch.backends.mps.is_available()
        except Exception as e:
            self.mpsAvailable = False

        try:
            pynvml.nvmlInit()
            device_count = pynvml.nvmlDeviceGetCount()
            if device_count > 0:
                self.useNVML = True
                self.nvmlHandle = pynvml.nvmlDeviceGetHandleByIndex(0)
            else:
                self.useNVML = False
                self.nvmlHandle = None
        except Exception as e:
            self.useNVML = False
            self.nvmlHandle = None

    def getGpuNames(self):
        try:
            if self.mpsAvailable:
                return [["mps", "Apple Silicon GPU (MPS)"]]
            if self.cudaAvailable:
                return [
                    [f"cuda:{i}", torch.cuda.get_device_name(i)]
                    for i in range(torch.cuda.device_count())
                ]
        except Exception as e:
            pass
        return []

    def getGpuPresent(self):
        return self.cudaAvailable or self.mpsAvailable

    def getGpuMemory(self) -> Tuple[float, float]:  # Return (total GB, available GB)
        try:
            if self.mpsAvailable:
                total_bytes = psutil.virtual_memory().total
                free_bytes = psutil.virtual_memory().available
                return float(toGB(total_bytes)), float(toGB(free_bytes))
            if self.cudaAvailable:
                free_bytes, total_bytes = torch.cuda.mem_get_info()
                return float(toGB(total_bytes)), float(toGB(free_bytes))
        except Exception as e:
            pass
        return None
    
    def getGpuMemeoryTotal(self) -> float:
        try:
            if self.mpsAvailable:
                total_bytes = psutil.virtual_memory().total
                return float(toGB(total_bytes))
            if self.cudaAvailable:
                free_bytes, total_bytes = torch.cuda.mem_get_info()
                return float(toGB(total_bytes))
        except Exception as e:
            pass
        return None
    
    def getGpuMemoryAvailable(self) -> float:
        try:
            if self.mpsAvailable:
                free_bytes = psutil.virtual_memory().available
                return float(toGB(free_bytes))
            if self.cudaAvailable:
                free_bytes, total_bytes = torch.cuda.mem_get_info()
                return float(toGB(free_bytes))
        except Exception as e:
            pass
        return None

    def getGpuUtilization(self) -> float:
        try:
            if self.mpsAvailable:
                return None
            if self.cudaAvailable and self.nvmlHandle:
                gpu_utilization = pynvml.nvmlDeviceGetUtilizationRates(self.nvmlHandle).gpu / 100.0
                return gpu_utilization
        except Exception as e:
            pass
        return None

def toGB(bytes):
    return bytes / (1024 * 1024 * 1024)
