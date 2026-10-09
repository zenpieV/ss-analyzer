$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot
if (-not $env:GEMINI_API_KEY) { Write-Host "NOTE: GEMINI_API_KEY not set. Overlay will show setup error until set." -ForegroundColor Yellow }
python "$PSScriptRoot\app.py" @args
