[CmdletBinding()]
param(
    [string]$Python,
    [string]$ModelsArchive,
    [string]$IsccPath,
    [string]$ModelBaseUrl,
    [string]$SignCommand
)

$ErrorActionPreference = 'Stop'
$repositoryDir = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$azureSettingNames = @(
    'WINDOWS_SIGNING_ENDPOINT',
    'WINDOWS_SIGNING_ACCOUNT',
    'WINDOWS_SIGNING_PROFILE'
)
$toolSettingNames = @(
    'WINDOWS_SIGNTOOL_PATH',
    'WINDOWS_SIGNING_DLIB_PATH',
    'WINDOWS_AZURE_CLI_PATH'
)
$settingNames = @('WINDOWS_SIGN_COMMAND') + $azureSettingNames + $toolSettingNames
$settings = @{}
$envFile = Join-Path $repositoryDir '.env'
if (Test-Path -LiteralPath $envFile -PathType Leaf) {
    foreach ($line in Get-Content -LiteralPath $envFile -Encoding UTF8) {
        if ($line -notmatch '^\s*(?:export\s+)?(WINDOWS_[A-Z0-9_]+)\s*=\s*(.*?)\s*$') { continue }
        $name, $value = $matches[1], $matches[2]
        if ($name -notin $settingNames) { continue }
        # Read literal assignments; never execute the shared macOS/Windows .env file.
        if ($value.Length -gt 0 -and $value[0] -in @([char]"'", [char]'"')) {
            if ($value.Length -lt 2 -or $value[-1] -ne $value[0]) {
                throw "Unclosed quote for $name in $envFile."
            }
            $value = $value.Substring(1, $value.Length - 2)
        }
        $settings[$name] = $value
    }
}
foreach ($name in $settingNames) {
    $value = [Environment]::GetEnvironmentVariable($name, 'Process')
    if ($null -ne $value) { $settings[$name] = $value }
}

$azureCliDirectory = $null
if (-not $PSBoundParameters.ContainsKey('SignCommand')) {
    if ($settings.ContainsKey('WINDOWS_SIGN_COMMAND')) {
        $SignCommand = $settings['WINDOWS_SIGN_COMMAND']
    } else {
        $missingSettings = @($azureSettingNames | Where-Object { [string]::IsNullOrWhiteSpace($settings[$_]) })
        if ($missingSettings.Count -gt 0) {
            throw "Configure Azure signing in .env (missing: $($missingSettings -join ', ')), set WINDOWS_SIGN_COMMAND, or pass -SignCommand."
        }
        $endpoint = $null
        if (-not [Uri]::TryCreate($settings['WINDOWS_SIGNING_ENDPOINT'], [UriKind]::Absolute, [ref]$endpoint) -or
            $endpoint.Scheme -ne 'https' -or -not $endpoint.Host) {
            throw 'WINDOWS_SIGNING_ENDPOINT must be an absolute HTTPS URL.'
        }
        if (-not $settings.ContainsKey('WINDOWS_SIGNTOOL_PATH')) {
            $command = Get-Command signtool.exe -CommandType Application -ErrorAction SilentlyContinue
            if ($command) {
                $settings['WINDOWS_SIGNTOOL_PATH'] = $command.Source
            } else {
                $sdkBin = Join-Path ${env:ProgramFiles(x86)} 'Windows Kits/10/bin'
                if (Test-Path -LiteralPath $sdkBin -PathType Container) {
                    $settings['WINDOWS_SIGNTOOL_PATH'] = Get-ChildItem -LiteralPath $sdkBin -Directory |
                        Where-Object { $_.Name -match '^\d+\.\d+\.\d+\.\d+$' } |
                        Sort-Object { [version]$_.Name } -Descending |
                        ForEach-Object { Join-Path $_.FullName 'x64/signtool.exe' } |
                        Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } |
                        Select-Object -First 1
                }
            }
        }
        if (-not $settings.ContainsKey('WINDOWS_SIGNING_DLIB_PATH')) {
            $settings['WINDOWS_SIGNING_DLIB_PATH'] = Join-Path $env:LOCALAPPDATA 'Microsoft/MicrosoftArtifactSigningClientTools/Azure.CodeSigning.Dlib.dll'
        }
        if (-not $settings.ContainsKey('WINDOWS_AZURE_CLI_PATH')) {
            $command = Get-Command az.cmd -CommandType Application -ErrorAction SilentlyContinue
            if ($command) {
                $settings['WINDOWS_AZURE_CLI_PATH'] = $command.Source
            } else {
                $settings['WINDOWS_AZURE_CLI_PATH'] = Join-Path $env:ProgramFiles 'Microsoft SDKs/Azure/CLI2/wbin/az.cmd'
            }
        }
        foreach ($name in $toolSettingNames) {
            $path = $settings[$name]
            if ([string]::IsNullOrWhiteSpace($path)) {
                throw "Could not find $name. Install the signing tools or set $name in .env."
            }
            if (-not [IO.Path]::IsPathRooted($path)) { $path = Join-Path $repositoryDir $path }
            if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
                throw "Signing prerequisite not found ($name): $path"
            }
            $settings[$name] = (Resolve-Path -LiteralPath $path).Path
        }
        $outputDir = Join-Path $repositoryDir 'out/windows'
        New-Item -ItemType Directory -Force -Path $outputDir | Out-Null
        $metadataPath = Join-Path $outputDir 'signing.json'
        $metadata = [ordered]@{
            Endpoint = $settings['WINDOWS_SIGNING_ENDPOINT']
            CodeSigningAccountName = $settings['WINDOWS_SIGNING_ACCOUNT']
            CertificateProfileName = $settings['WINDOWS_SIGNING_PROFILE']
        }
        # The signing client's JSON reader rejects a UTF-8 byte-order mark.
        $utf8WithoutBom = [Text.UTF8Encoding]::new($false)
        [IO.File]::WriteAllText($metadataPath, ($metadata | ConvertTo-Json) + [Environment]::NewLine, $utf8WithoutBom)

        $azureCliDirectory = Split-Path $settings['WINDOWS_AZURE_CLI_PATH'] -Parent
        # Escape literal dollars before introducing Inno's $q and $f placeholders.
        $literalPaths = @($settings['WINDOWS_SIGNTOOL_PATH'], $settings['WINDOWS_SIGNING_DLIB_PATH'], $metadataPath) |
            ForEach-Object { $_.Replace('$', '$$') }
        $SignCommand = (
            '$q{0}$q sign /fd SHA256 /tr http://timestamp.acs.microsoft.com /td SHA256 ' +
            '/dlib $q{1}$q /dmdf $q{2}$q $f'
        ) -f $literalPaths
    }
}
if ([string]::IsNullOrWhiteSpace($SignCommand)) {
    throw 'Set WINDOWS_SIGN_COMMAND or pass -SignCommand with an Inno signing command to build a signed Windows release.'
}

# Forward only supplied options so build.ps1 owns the build defaults.
$PSBoundParameters['SignCommand'] = $SignCommand
$previousPath = $env:PATH
try {
    if ($azureCliDirectory) { $env:PATH = "$azureCliDirectory;$previousPath" }
    & (Join-Path $PSScriptRoot 'build.ps1') @PSBoundParameters
} finally {
    $env:PATH = $previousPath
}
