# Script de démarrage WeaveGuard AI pour le développement et la démonstration
# Utilisation : .\scripts\start_dev.ps1 [-HostAddress <ip>] [-Port <port>]

param (
    [string]$HostAddress = "127.0.0.1",
    [int]$Port = 8000
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root "backend\.venv\Scripts\python.exe"
$CheckMongo = Join-Path $Root "backend\scripts\check_mongo.py"

if (-not (Test-Path $Python)) {
    Write-Error "Environnement virtuel Python introuvable : $Python"
    exit 1
}

Write-Host "================================================================" -ForegroundColor Cyan
Write-Host " WeaveGuard AI — Démarrage de la plateforme (Mode Démonstration)" -ForegroundColor Cyan
Write-Host "================================================================" -ForegroundColor Cyan

# 1. Vérification de la disponibilité de MongoDB
Write-Host "`n[1/2] Vérification de MongoDB..." -ForegroundColor Yellow
$env:PYTHONPATH = (Join-Path $Root "backend")
& $Python $CheckMongo
if ($LASTEXITCODE -ne 0) {
    Write-Error "Échec de la connexion à MongoDB. Veuillez vérifier que le service MongoDB local est actif."
    exit 1
}

# 2. Lancement du serveur d'API FastAPI (uvicorn sans --reload)
Write-Host "`n[2/2] Lancement du serveur API FastAPI..." -ForegroundColor Yellow
Write-Host "Documentation OpenAPI / Swagger disponible sur : " -NoNewline
Write-Host "http://${HostAddress}:${Port}/docs" -ForegroundColor Green
Write-Host "Health check disponible sur : " -NoNewline
Write-Host "http://${HostAddress}:${Port}/health" -ForegroundColor Green
Write-Host "`nAppuyez sur Ctrl+C pour arrêter le serveur.`n" -ForegroundColor DarkGray

& $Python -m uvicorn app.main:app --app-dir (Join-Path $Root "backend") --host $HostAddress --port $Port

