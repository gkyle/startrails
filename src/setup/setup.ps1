[CmdletBinding()]
param(
    [switch]$Packaged,
    [switch]$Launch,
    [switch]$Repair,
    [AllowEmptyString()][string]$ProjectPath
)

$ErrorActionPreference = 'Stop'
$applicationDir = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$transcribing = $false
$pushedLocation = $false
$setupLockStream = $null

function Invoke-Uv {
    param([string]$Executable, [string[]]$Arguments, [switch]$RetryPythonLinkFailure)
    # Capture native stderr as well as stdout: Windows PowerShell transcripts alone
    # omit native diagnostics, and a successful probe may write warnings to stderr.
    $ErrorActionPreference = 'Continue'
    while ($true) {
        $lines = [System.Collections.Generic.List[object]]::new()
        $global:LASTEXITCODE = $null
        & $Executable @Arguments 2>&1 | ForEach-Object {
            $lines.Add($_)
            # Keep diagnostics out of captured results such as the GPU variant,
            # but display them immediately while downloads are still running.
            if ($_ -is [System.Management.Automation.ErrorRecord]) { Write-Host $_.ToString() }
            else { Write-Output $_ }
        }
        $exitCode = $global:LASTEXITCODE
        if ($exitCode -eq 0) { return }
        if (-not $RetryPythonLinkFailure -or
            "$lines" -notmatch 'Failed to create Python minor version link directory' -or
            "$lines" -notmatch 'os error 448') {
            throw "uv failed (exit $exitCode). $($lines -join [Environment]::NewLine)"
        }
        # uv finishes installing the pinned patch version before creating its optional
        # minor-version junction. A retry discovers that interpreter without downloading
        # it or recreating the junction (astral-sh/uv#19616).
        $RetryPythonLinkFailure = $false
        Write-Host 'Windows blocked the optional Python version junction. Retrying with the installed interpreter...'
    }
}

try {
    # Preserve relative project arguments before setup changes directories.
    if ($ProjectPath) {
        $ProjectPath = [System.IO.Path]::GetFullPath($ProjectPath)
    }
    Push-Location -LiteralPath $applicationDir
    $pushedLocation = $true

    if ($Packaged) {
        $release = Get-Content -LiteralPath (Join-Path $applicationDir 'release.json') -Raw | ConvertFrom-Json
        $uv = Join-Path $applicationDir 'tools/uv.exe'
        $runtimeDir = Join-Path $applicationDir 'runtime'
        $environmentDir = Join-Path $runtimeDir 'venv'
        $pythonw = Join-Path $environmentDir 'Scripts/pythonw.exe'
        $readyFile = Join-Path $runtimeDir 'ready.json'
        $env:UV_PROJECT_ENVIRONMENT = $environmentDir
        $env:UV_PYTHON_INSTALL_DIR = Join-Path $runtimeDir 'python'
        $env:UV_CACHE_DIR = Join-Path $runtimeDir 'cache'
        $env:UV_PYTHON_PREFERENCE = 'only-managed'
        $env:UV_PYTHON_INSTALL_BIN = '0'
        $env:UV_PYTHON_NO_REGISTRY = '1'
        if (-not (Test-Path Env:STARTRAILS_WORK_DIR)) {
            $env:STARTRAILS_WORK_DIR = Join-Path ([Environment]::GetFolderPath('MyDocuments')) 'Startrails'
        }

        $ready = $false
        if (-not $Repair -and (Test-Path -LiteralPath $readyFile) -and (Test-Path -LiteralPath $pythonw)) {
            $installed = Get-Content -LiteralPath $readyFile -Raw | ConvertFrom-Json
            $lockHash = (Get-FileHash -LiteralPath 'uv.lock' -Algorithm SHA256).Hash
            $ready = $installed.release_id -eq $release.release_id -and $installed.lock_hash -eq $lockHash
        }
        $needsSetup = $Repair -or -not $ready
        if ($Launch -and -not $Repair -and -not $ready) {
            throw 'The installed environment needs repair. Open Repair StarTrails AI from the Start menu.'
        }
        if ($needsSetup) {
            New-Item -ItemType Directory -Force -Path $runtimeDir | Out-Null
            $setupLock = Join-Path $runtimeDir '.setup-lock'
            try {
                $setupLockStream = [System.IO.File]::Open(
                    $setupLock,
                    [System.IO.FileMode]::OpenOrCreate,
                    [System.IO.FileAccess]::ReadWrite,
                    [System.IO.FileShare]::None
                )
            } catch [System.IO.IOException] {
                throw 'Another setup is running. Wait for it to finish before running Repair StarTrails AI.'
            }
            Start-Transcript -LiteralPath (Join-Path $runtimeDir 'setup.log') -Force | Out-Null
            $transcribing = $true
            # A failed repair must not leave a readiness marker for a partial environment.
            if (Test-Path -LiteralPath $readyFile) { Remove-Item -LiteralPath $readyFile -Force }
            $uvVersion = Invoke-Uv -Executable $uv -Arguments @('--version')
            if ($uvVersion -notmatch ('^uv ' + [regex]::Escape($release.uv_version) + '( |$)')) {
                throw 'The bundled uv executable does not match this release. Please reinstall StarTrails AI.'
            }
        }
    } else {
        $needsSetup = $true
        Write-Host 'Checking for uv...'
        if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
            Invoke-RestMethod 'https://astral.sh/uv/install.ps1' | Invoke-Expression
            $env:PATH += ";$env:USERPROFILE\.local\bin"
            if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
                throw 'uv installation failed.'
            }
        } else {
            & uv self update
            if ($LASTEXITCODE -ne 0) {
                Write-Warning 'Could not update uv; continuing with the installed version.'
            }
        }
        $uv = (Get-Command uv -CommandType Application | Select-Object -First 1).Source
    }

    if ($needsSetup) {
        Write-Host 'Preparing Python and checking GPU support...'
        $runArgs = @('run')
        if ($Packaged) {
            $runArgs += @('--no-project', '--python', $release.python_version)
        } else {
            $runArgs += '--no-sync'
        }
        $torchVariant = Invoke-Uv -Executable $uv -Arguments ($runArgs + @('--', 'src/setup/probeGPU.py')) -RetryPythonLinkFailure:$Packaged
        # Read supported variants from the dependency policy instead of maintaining another list.
        Invoke-Uv -Executable $uv -Arguments ($runArgs + @('--', 'src/setup/check_setup.py', '--variant', $torchVariant)) |
            ForEach-Object { Write-Host $_ }
        Write-Host "Using torch variant: $torchVariant"
        if ($torchVariant -eq 'cpu') {
            Write-Host 'No compatible GPU was found. CPU processing will be available. Re-run setup after installing drivers to enable GPU support.'
        }
        $syncArgs = @('sync', '--extra', $torchVariant)
        if ($Packaged) {
            $syncArgs += @('--locked', '--python', $release.python_version)
        }
        Write-Host 'Downloading and installing dependencies...'
        Invoke-Uv -Executable $uv -Arguments $syncArgs | ForEach-Object { Write-Host $_ }
        $checkArgs = @('run', '--no-sync')
        if ($Packaged) { $checkArgs += @('--python', $release.python_version) }
        $checkArgs += @('--', 'src/setup/check_runtime.py', '--variant', $torchVariant)
        if ($Packaged) { $checkArgs += @('--notice-file', (Join-Path $runtimeDir 'prerequisites.txt')) }
        Write-Host 'Checking the installed environment...'
        Invoke-Uv -Executable $uv -Arguments $checkArgs | ForEach-Object { Write-Host $_ }
        if ($Packaged) {
            if (-not (Test-Path -LiteralPath $pythonw)) {
                throw 'The Python environment is incomplete. Please retry setup.'
            }
            @{
                release_id = $release.release_id
                lock_hash = (Get-FileHash -LiteralPath 'uv.lock' -Algorithm SHA256).Hash
                torch_variant = $torchVariant
            } | ConvertTo-Json | Set-Content -LiteralPath $readyFile -Encoding UTF8
        }
        Write-Host 'Python and dependencies are ready.'
    }

    if ($Launch) {
        Write-Host 'Starting StarTrails AI...'
        if ($Packaged) {
            $launchArgs = @('"' + (Join-Path $applicationDir 'src/main.py') + '"')
            if ($ProjectPath) { $launchArgs += '"' + $ProjectPath + '"' }
            Start-Process -FilePath $pythonw -ArgumentList $launchArgs -WorkingDirectory $applicationDir -WindowStyle Hidden
        } else {
            $launchArgs = @('run', '--no-sync', '--', 'src/main.py')
            if ($ProjectPath) { $launchArgs += $ProjectPath }
            & $uv @launchArgs
            if ($LASTEXITCODE -ne 0) { throw "StarTrails AI exited with code $LASTEXITCODE." }
        }
    }
} catch {
    Write-Error -Message $_ -ErrorAction Continue
    if ($Packaged -and $Launch) {
        Add-Type -AssemblyName System.Windows.Forms
        [System.Windows.Forms.MessageBox]::Show(
            "Could not start StarTrails AI.`n$($_.Exception.Message)`nSee runtime\setup.log in the installed release directory.",
            'StarTrails AI'
        ) | Out-Null
    }
    exit 1
} finally {
    if ($transcribing) { Stop-Transcript | Out-Null }
    if ($setupLockStream) { $setupLockStream.Dispose() }
    if ($pushedLocation) { Pop-Location }
}
