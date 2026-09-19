\
$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$Upstream = Join-Path $Root "upstream"
$Amane = Join-Path $Upstream "amane"

New-Item -ItemType Directory -Force -Path $Upstream | Out-Null

if (Test-Path $Amane) {
    Write-Host "upstream\amane already exists. No changes made."
    exit 0
}

git clone https://github.com/sqzw-x/amane.git $Amane
Push-Location $Amane
git checkout v0.15.0
git rev-parse HEAD
Pop-Location

Write-Host "Amane v0.15.0 cloned as read-only reference target."
