[CmdletBinding()]
param(
    [string]$Python = 'python',
    [string]$ModelsArchive,
    [string]$IsccPath,
    [string]$ModelBaseUrl,
    [string]$SignCommand,
    [switch]$StageOnly
)

$ErrorActionPreference = 'Stop'
$repositoryDir = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
if (-not $ModelsArchive) {
    $ModelsArchive = & $Python (Join-Path $repositoryDir 'build/models.py') --download
    if ($LASTEXITCODE -ne 0) { throw 'Could not fetch the published model archive from GitHub.' }
}
if (-not (Test-Path -LiteralPath $ModelsArchive -PathType Leaf)) {
    throw "Model archive not found: $ModelsArchive."
}
$modelsArchivePath = (Resolve-Path -LiteralPath $ModelsArchive).Path
$toolchain = Get-Content -LiteralPath (Join-Path $repositoryDir 'build/toolchain.json') -Raw | ConvertFrom-Json
$downloadsDir = Join-Path $repositoryDir 'out/windows/downloads'
New-Item -ItemType Directory -Force -Path $downloadsDir | Out-Null
$uvArchive = Join-Path $downloadsDir "uv-$($toolchain.uv_version).zip"
$uvUrl = "https://github.com/astral-sh/uv/releases/download/$($toolchain.uv_version)/uv-x86_64-pc-windows-msvc.zip"
if (-not (Test-Path -LiteralPath $uvArchive)) {
    Invoke-WebRequest -UseBasicParsing -Uri $uvUrl -OutFile $uvArchive
}
if ((Get-FileHash -LiteralPath $uvArchive -Algorithm SHA256).Hash -ne $toolchain.windows_x64_uv_archive_sha256) {
    throw "uv download failed verification. Remove '$uvArchive' and retry the build."
}
$uvDir = Join-Path $downloadsDir "uv-$($toolchain.uv_version)"
Expand-Archive -LiteralPath $uvArchive -DestinationPath $uvDir -Force
foreach ($licenseName in @('LICENSE-MIT', 'LICENSE-APACHE')) {
    $licenseFile = Join-Path $uvDir $licenseName
    if (-not (Test-Path -LiteralPath $licenseFile)) {
        Invoke-WebRequest -UseBasicParsing -Uri "https://raw.githubusercontent.com/astral-sh/uv/$($toolchain.uv_version)/$licenseName" -OutFile $licenseFile
    }
}
$uv = Join-Path $uvDir 'uv.exe'
$versionOutput = & $uv --version
if ($LASTEXITCODE -ne 0 -or $versionOutput -notmatch ('^uv ' + [regex]::Escape($toolchain.uv_version) + '( |$)')) {
    throw 'The downloaded uv executable does not match toolchain.json.'
}

Push-Location -LiteralPath $repositoryDir
$previousCache = $env:UV_CACHE_DIR
try {
    $env:UV_CACHE_DIR = Join-Path $downloadsDir 'cache'
    & $uv lock --check --offline
    if ($LASTEXITCODE -ne 0) { throw 'Update uv.lock from the repository before building the installer.' }
    $buildId = [Guid]::NewGuid().ToString('N')
    $outputDir = Join-Path $repositoryDir "out/windows/build-$buildId"
    $prepareArgs = @((Join-Path $PSScriptRoot 'prepare.py'), '--output', $outputDir, '--uv-executable', $uv, '--models-archive', $modelsArchivePath)
    if ($ModelBaseUrl) { $prepareArgs += @('--model-base-url', $ModelBaseUrl) }
    $result = & $Python @prepareArgs
    if ($LASTEXITCODE -ne 0) { throw 'Could not stage the Windows release.' }
    $release = $result | ConvertFrom-Json
    Write-Host "Staged $($release.release_id) in $outputDir"
    if ($StageOnly) { return }

    if (-not $IsccPath) {
        $compiler = Get-Command ISCC.exe -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($compiler) { $IsccPath = $compiler.Source }
        else {
            $IsccPath = Join-Path ${env:ProgramFiles(x86)} 'Inno Setup 6/ISCC.exe'
        }
    }
    if (-not (Test-Path -LiteralPath $IsccPath)) {
        throw 'Install Inno Setup 6.7.1 or later and pass -IsccPath to ISCC.exe.'
    }
    $compileArgs = @("/DStageDir=$outputDir", "/O$outputDir")
    if ($SignCommand) { $compileArgs += @('/DSignedBuild', "/Sstartrails=$SignCommand") }
    $compileArgs += Join-Path $PSScriptRoot 'installer.iss'
    & $IsccPath @compileArgs
    if ($LASTEXITCODE -ne 0) { throw 'Inno Setup compilation failed.' }
    $installer = Join-Path $outputDir "StarTrailsAI-$($release.version)-windows-x64-setup.exe"
    if ($SignCommand) {
        $signature = Get-AuthenticodeSignature -LiteralPath $installer
        if ($signature.Status -ne 'Valid') {
            throw "Installer signature verification failed ($($signature.Status)): $($signature.StatusMessage)"
        }
    }
    $installerHash = (Get-FileHash -LiteralPath $installer -Algorithm SHA256).Hash.ToLowerInvariant()
    Add-Content -LiteralPath (Join-Path $outputDir 'SHA256SUMS') -Value "$installerHash  $([IO.Path]::GetFileName($installer))" -Encoding ASCII
    Write-Host "Installer, models, and checksums: $outputDir"
    if ($SignCommand) {
        & $Python (Join-Path $repositoryDir 'build/publish.py') --version $release.version $installer
        if ($LASTEXITCODE -ne 0) { throw 'GitHub Release sync failed.' }
    }
} finally {
    $env:UV_CACHE_DIR = $previousCache
    Pop-Location
}
