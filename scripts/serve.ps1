param(
    [ValidateRange(1, 65535)]
    [int]$Port = 8000
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location -LiteralPath $projectRoot
try {
    Write-Host "Tokyo: http://127.0.0.1:$Port/"
    Write-Host "Osaka: http://127.0.0.1:$Port/?region=osaka"
    Write-Host 'Stop with Ctrl+C.'
    uv run --offline --frozen python -m http.server --bind 127.0.0.1 --directory web $Port
    if ($LASTEXITCODE -ne 0) {
        throw "Local server exited with code $LASTEXITCODE."
    }
}
finally {
    Pop-Location
}
