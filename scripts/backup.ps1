# Script PowerShell de sauvegarde WeaveGuard AI
# Utilisation : .\scripts\backup.ps1 [-Db <nom_base>] [-Out <dossier_destination>] [-NoStorage]

param (
    [string]$Db = "weaveguard",
    [string]$Out = "",
    [switch]$NoStorage
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root "backend\.venv\Scripts\python.exe"
$BackupScript = Join-Path $Root "backend\scripts\db_backup.py"

if (-not (Test-Path $Python)) {
    Write-Error "Environnement virtuel Python introuvable : $Python"
    exit 1
}

$Arguments = @($BackupScript, "--db", $Db)
if ($Out) {
    $Arguments += @("--out", $Out)
}
if ($NoStorage) {
    $Arguments += "--no-storage"
}

Write-Host "Lancement de la sauvegarde WeaveGuard AI..." -ForegroundColor Cyan
& $Python $Arguments
if ($LASTEXITCODE -eq 0) {
    Write-Host "Sauvegarde terminee avec succes." -ForegroundColor Green
} else {
    Write-Error "Echec de la sauvegarde (code $LASTEXITCODE)."
}

