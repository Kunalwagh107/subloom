param([switch]$DownloadRuntime, [switch]$Installer, [switch]$SkipAppBuild, [string]$Python)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location -LiteralPath $projectRoot
try {
    $buildPython = if ($Python) { $Python } elseif (Test-Path -LiteralPath (Join-Path $projectRoot '.venv/Scripts/python.exe')) {
        Join-Path $projectRoot '.venv/Scripts/python.exe'
    } else { (Get-Command python -ErrorAction Stop).Source }
    $version = & $buildPython -c 'from subloom import __version__; print(__version__)'
    if ($LASTEXITCODE -ne 0 -or $version -notmatch '^\d+\.\d+\.\d+$') { throw 'Install the local .[dev] package before building.' }
    $portableRoot = [IO.Path]::GetFullPath((Join-Path $projectRoot ('dist/portable/' + $version)))
    $expectedBoundary = [IO.Path]::GetFullPath((Join-Path $projectRoot 'dist')) + [IO.Path]::DirectorySeparatorChar
    if (-not $portableRoot.StartsWith($expectedBoundary, [StringComparison]::OrdinalIgnoreCase)) { throw 'Invalid build output path.' }
    $appPath = Join-Path $portableRoot 'Subloom/Subloom.exe'
    foreach ($running in (Get-Process Subloom -ErrorAction SilentlyContinue)) {
        if ($running.Path -eq $appPath) { throw 'This version is running. Close it before rebuilding the same version.' }
    }
    if ($DownloadRuntime) {
        & $buildPython scripts/bootstrap_runtime.py --download
        if ($LASTEXITCODE -ne 0) { throw 'Runtime installation failed.' }
    }
    if (-not $SkipAppBuild) {
        & $buildPython -m PyInstaller --noconfirm --distpath $portableRoot packaging/Subloom.spec
        if ($LASTEXITCODE -ne 0) { throw 'Packaging failed.' }
    }
    if (-not (Test-Path -LiteralPath $appPath)) { throw 'The portable application has not been built.' }
    $appDirectory = Split-Path -Parent $appPath
    foreach ($name in @('README.md', 'LICENSE', 'CONTRIBUTING.md')) {
        Copy-Item -LiteralPath (Join-Path $projectRoot $name) -Destination $appDirectory -Force
    }
    $docsDirectory = Join-Path $appDirectory 'docs'
    New-Item -ItemType Directory -Path $docsDirectory -Force | Out-Null
    Get-ChildItem -LiteralPath (Join-Path $projectRoot 'docs') -Filter '*.md' -File |
        Copy-Item -Destination $docsDirectory -Force
    $publicAssets = Join-Path $projectRoot 'docs/assets'
    if (Test-Path -LiteralPath $publicAssets) {
        $assetsDestination = Join-Path $docsDirectory 'assets'
        New-Item -ItemType Directory -Path $assetsDestination -Force | Out-Null
        foreach ($name in @('subloom-banner.svg', 'subloom-banner.png', 'subloom-logo.svg', 'subloom-logo.png',
                            'welcome.png', 'editor.png', 'models.png', 'subloom-demo.gif', 'subloom-demo.mp4', 'README.md')) {
            $asset = Join-Path $publicAssets $name
            if (Test-Path -LiteralPath $asset -PathType Leaf) { Copy-Item -LiteralPath $asset -Destination $assetsDestination -Force }
        }
    }
    if ($Installer) {
        $compiler = if ($env:ISCC_PATH) { $env:ISCC_PATH } elseif (Get-Command ISCC -ErrorAction SilentlyContinue) {
            (Get-Command ISCC).Source
        } else { Join-Path $projectRoot '.tools/inno/ISCC.exe' }
        if (-not (Test-Path -LiteralPath $compiler)) { throw 'Install Inno Setup 6.7.3 and set ISCC_PATH to ISCC.exe.' }
        & $compiler /Q ('/DAppVersion=' + $version) packaging/Subloom.iss
        if ($LASTEXITCODE -ne 0) { throw 'Core installer compilation failed.' }
        if (Test-Path -LiteralPath '.tools/runtime/gpu/whisper-cli.exe') {
            & $compiler /Q ('/DAppVersion=' + $version) packaging/SubloomGPU.iss
            if ($LASTEXITCODE -ne 0) { throw 'NVIDIA add-on installer compilation failed.' }
        }
        Write-Output 'Windows installers: dist/installers. No Python or venv is required by users.'
    }
    Write-Output ('Portable Windows application: ' + $appPath + ' (keep the whole folder together).')
} finally { Pop-Location }
