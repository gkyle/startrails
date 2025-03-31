try {
    Set-ExecutionPolicy RemoteSigned -scope CurrentUser
    Write-Host "Checking for uv..."
    Invoke-Expression -Command "uv -V"
} catch {
    Invoke-Expression -Command  "irm https://astral.sh/uv/install.ps1 | iex"
    $env:PATH += ";$env:USERPROFILE\.local\bin"
}

$torch_variant = Invoke-Expression -Command "uv run src/setup/probeGPU.py"
Write-Host "Using torch variant: $torch_variant"
if ($torch_variant.Length -eq 0 -or $torch_variant -Match "not found") {
    $torch_variant = "cpu"
}
if ($torch_variant -eq "cpu") {
    Write-Host "Install did not find a CUDA compatible GPU. Install will continue with CPU-only dependencies. You can re-run install.bat after installing drivers or CUDA Toolkit to enable GPU support."
}

Invoke-Expression -Command "uv sync --extra $torch_variant"
