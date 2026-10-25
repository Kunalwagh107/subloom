param([switch]$Apply, [switch]$IncludeDownloads, [switch]$IncludeTestRuns, [switch]$BuildOutput)
$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$boundary = $root + [IO.Path]::DirectorySeparatorChar
$targets = @()
foreach ($name in @('.pytest_cache', '.ruff_cache', '.mypy_cache')) { $targets += Join-Path $root $name }
foreach ($name in @('src', 'tests', 'scripts')) {
    $targets += Get-ChildItem -LiteralPath (Join-Path $root $name) -Directory -Recurse -Filter '__pycache__' | Select-Object -ExpandProperty FullName
}
if ($IncludeDownloads -and (Test-Path -LiteralPath (Join-Path $root '.tools'))) {
    $targets += Get-ChildItem -LiteralPath (Join-Path $root '.tools') -Force |
        Where-Object { $_.Name -notin @('runtime', 'inno') } | Select-Object -ExpandProperty FullName
    foreach ($name in @('ffplay.exe', 'SDL2.dll')) { $targets += Join-Path $root ('.tools/runtime/' + $name) }
}
if ($IncludeTestRuns -and (Test-Path -LiteralPath (Join-Path $root '.test-data'))) {
    $targets += Get-ChildItem -LiteralPath (Join-Path $root '.test-data') -Force |
        Where-Object { $_.Name -notin @('models', 'corpus') } | Select-Object -ExpandProperty FullName
}
if ($BuildOutput) { $targets += Join-Path $root 'build' }
$verified = @()
foreach ($target in ($targets | Sort-Object -Unique)) {
    if (-not (Test-Path -LiteralPath $target)) { continue }
    $absolute = [IO.Path]::GetFullPath((Resolve-Path -LiteralPath $target).ProviderPath)
    if (-not $absolute.StartsWith($boundary, [StringComparison]::OrdinalIgnoreCase)) { throw "Refusing target outside project: $absolute" }
    $item = Get-Item -LiteralPath $absolute -Force
    if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw "Refusing linked cleanup target: $absolute" }
    if ($item.PSIsContainer) {
        $linked = Get-ChildItem -LiteralPath $absolute -Directory -Force -Recurse |
            Where-Object { $_.Attributes -band [IO.FileAttributes]::ReparsePoint } | Select-Object -First 1
        if ($linked) { throw "Refusing directory containing a link: $absolute" }
    }
    $verified += $absolute
}
foreach ($absolute in $verified) {
    if ($Apply) {
        Remove-Item -LiteralPath $absolute -Recurse -Force
        Write-Output ('Removed: ' + $absolute)
    } else { Write-Output ('Would remove: ' + $absolute) }
}
if (-not $Apply) { Write-Output 'Preview only. Pass -Apply to remove these generated artifacts.' }
