# Script PowerShell de restauration WeaveGuard AI
# Utilisation : .\scripts\restore.ps1 -BackupDir <chemin_backup> -TargetDb <nom_base> [-RestoreStorage]

param (
    [Parameter(Mandatory=$true)]
    [string]$BackupDir,
    [Parameter(Mandatory=$true)]
    [string]$TargetDb,
    [switch]$RestoreStorage
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root "backend\.venv\Scripts\python.exe"
$RestoreScript = Join-Path $Root "backend\scripts\db_restore.py"

if (-not (Test-Path $Python)) {
    Write-Error "Environnement virtuel Python introuvable : $Python"
    exit 1
}

$Arguments = @($RestoreScript, "--backup-dir", $BackupDir, "--target-db", $TargetDb)
if ($RestoreStorage) {
    $Arguments += "--restore-storage"
}

Write-Host "Lancement de la restauration WeaveGuard AI..." -ForegroundColor Cyan
& $Python $Arguments
if ($LASTEXITCODE -eq 0) {
    Write-Host "Restauration terminee avec succes." -ForegroundColor Green
} else {
    Write-Error "Echec de la restauration (code $LASTEXITCODE)."
}

