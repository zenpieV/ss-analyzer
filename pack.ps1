# Build a shippable ss-analyzer zip from a manifest — personal files can never leak in.
$ErrorActionPreference = "Stop"
$root = $PSScriptRoot

$m = Select-String -Path "$root\app.py" -Pattern '^VERSION = "(.*)"$'
$version = if ($m) { $m.Matches[0].Groups[1].Value } else { "dev" }

$ship = @(
    "app.py",
    "SS-Analyzer.bat",
    "run.ps1",
    "requirements.txt",
    "README.md",
    "THEMES.md",
    "go_models_live.json",
    ".gitignore"
)

$zip = "$root\ss-analyzer-v$version.zip"
if (Test-Path -LiteralPath $zip) { Remove-Item -LiteralPath $zip -Force }

$stage = Join-Path ([System.IO.Path]::GetTempPath()) "ss-pack"
if (Test-Path -LiteralPath $stage) { Get-ChildItem -LiteralPath $stage | Remove-Item -Force }
New-Item -ItemType Directory -Path $stage -Force | Out-Null
foreach ($f in $ship) {
    $src = Join-Path $root $f
    if (-not (Test-Path -LiteralPath $src)) { throw "manifest file missing: $f" }
    Copy-Item -LiteralPath $src -Destination (Join-Path $stage $f) -Force
}
# Guard: fail if a personal file would sneak in (belt and suspenders).
foreach ($bad in @("config.json", "settings.json", "analyses.md", "crash.log")) {
    if (Get-ChildItem -LiteralPath $stage -Filter $bad -ErrorAction SilentlyContinue) {
        throw "personal file in stage: $bad"
    }
}
Compress-Archive -Path (Join-Path $stage "*") -DestinationPath $zip -Force
Get-ChildItem -LiteralPath $stage | Remove-Item -Force
Write-Host "Packed: $zip"
Get-ChildItem -LiteralPath $zip | Select-Object Name, Length | Out-String
