Write-Host "Checking for uv..."
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    irm https://astral.sh/uv/install.ps1 | iex
    $env:PATH += ";$env:USERPROFILE\.local\bin"
    if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
        throw "uv installation failed."
    }
} else {
    uv self update
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "Could not update uv; continuing with the installed version."
    }
}

$torch_variant = Invoke-Expression -Command "uv run --no-sync src/setup/probeGPU.py"
Write-Host "Using torch variant: $torch_variant"
if ($torch_variant.Length -eq 0 -or $torch_variant -Match "not found") {
    $torch_variant = "cpu"
}
if ($torch_variant -eq "cpu") {
    Write-Host "Setup did not find a compatible GPU. Setup will continue with CPU-only dependencies. You can re-run after installing drivers to enable GPU support."
}

Invoke-Expression -Command "uv sync --extra $torch_variant"
