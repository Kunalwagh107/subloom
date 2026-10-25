param([string]$TestDirectory = '.test-data/installer-check')
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$versionSource = Get-Content -LiteralPath (Join-Path $projectRoot 'src/subloom/__init__.py') -Raw
if ($versionSource -notmatch '__version__\s*=\s*"([0-9]+\.[0-9]+\.[0-9]+)"') { throw 'Cannot read application version.' }
$version = $Matches[1]
$testRoot = [IO.Path]::GetFullPath((Join-Path $projectRoot $TestDirectory))
$allowed = [IO.Path]::GetFullPath((Join-Path $projectRoot '.test-data')) + [IO.Path]::DirectorySeparatorChar
if (-not $testRoot.StartsWith($allowed, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Installer validation must stay inside this project .test-data directory.'
}
$corePath = Join-Path $testRoot 'Application'
$profilePath = Join-Path $testRoot 'Profile'
$gpuPath = Join-Path $profilePath 'runtimes/gpu'
$ids = @('{F575CD9A-8647-42B8-981F-99F00B33D772}_is1', '{DB9D604D-0D93-495C-9875-127B5D10797F}_is1')
foreach ($id in $ids) {
    $registered = Get-ItemProperty -LiteralPath ('HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\' + $id) -ErrorAction SilentlyContinue
    if ($registered.InstallLocation -and -not ([IO.Path]::GetFullPath($registered.InstallLocation)).StartsWith($allowed, [StringComparison]::OrdinalIgnoreCase)) {
        throw 'An existing user installation is registered. Use a separate VM for installer validation.'
    }
}
New-Item -ItemType Directory -Force -Path $testRoot | Out-Null
$previousProfile = $env:SUBLOOM_DATA_DIR
$previousPlatform = $env:QT_QPA_PLATFORM
try {
    foreach ($pair in @(@("Subloom-Setup-$version.exe", $corePath), @("Subloom-NVIDIA-Setup-$version.exe", $gpuPath))) {
        $setup = Join-Path $projectRoot ('dist/installers/' + $pair[0])
        $args = @('/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/NOICONS', ('/DIR="' + $pair[1] + '"'))
        $process = Start-Process -FilePath $setup -ArgumentList $args -WindowStyle Hidden -Wait -PassThru
        if ($process.ExitCode -ne 0) { throw ('Installer failed: ' + $pair[0] + ' exit ' + $process.ExitCode) }
    }
    foreach ($document in @('README.md', 'LICENSE', 'docs/USER_GUIDE.md', 'docs/THIRD_PARTY.md', 'docs/DEVELOPMENT.md')) {
        if (-not (Test-Path -LiteralPath (Join-Path $corePath $document))) {
            throw ('Installed documentation is missing: ' + $document)
        }
    }
    $env:SUBLOOM_DATA_DIR = $profilePath
    $env:QT_QPA_PLATFORM = 'offscreen'
    $report = Join-Path $testRoot 'installed-smoke.json'
    $app = Start-Process -FilePath (Join-Path $corePath 'Subloom.exe') -ArgumentList @('--smoke-test', ('"' + $report + '"')) -WindowStyle Hidden -PassThru
    if (-not $app.WaitForExit(30000)) { Stop-Process -Id $app.Id; throw 'Installed application smoke timed out.' }
    if ($app.ExitCode -ne 0) { throw 'Installed application failed to launch.' }
    $result = Get-Content -LiteralPath $report -Raw | ConvertFrom-Json
    if (-not $result.qml_loaded -or -not $result.frozen -or -not $result.gpu_runtime_detected -or $result.version -ne $version) {
        throw 'Installed application diagnostic did not validate QML, version and GPU runtime.'
    }
    Write-Output 'Both installers and the installed application passed the launch check.'
    Write-Output ('Report: ' + $report)
} finally {
    $env:SUBLOOM_DATA_DIR = $previousProfile
    $env:QT_QPA_PLATFORM = $previousPlatform
    foreach ($target in @($gpuPath, $corePath)) {
        $resolved = [IO.Path]::GetFullPath($target)
        if (-not $resolved.StartsWith($testRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
            throw 'Refusing an uninstaller outside the verified test directory.'
        }
        $uninstaller = Join-Path $resolved 'unins000.exe'
        if (Test-Path -LiteralPath $uninstaller) {
            $cleanup = Start-Process -FilePath $uninstaller -ArgumentList @('/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART') -WindowStyle Hidden -Wait -PassThru
            if ($cleanup.ExitCode -ne 0) { Write-Warning ('Test installation cleanup failed: ' + $resolved) }
        }
    }
}
