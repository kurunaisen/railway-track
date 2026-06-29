#Requires -Version 5.1
<#
.SYNOPSIS
  Установка Railway Track Inspection на Windows.
#>
param(
    [switch]$WithWorker,
    [switch]$SkipFrontend
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
if (-not (Test-Path "$Root\backend")) { $Root = $PSScriptRoot + "\.." }

Write-Host "=== Railway Track Inspection — установка (Windows) ===" -ForegroundColor Cyan

# ffmpeg
if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
    Write-Warning "ffmpeg не найден в PATH. Установите: winget install Gyan.FFmpeg"
} else {
    Write-Host "[OK] ffmpeg" -ForegroundColor Green
}

# Python backend
Set-Location "$Root\backend"
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Создан backend\.env (AUTH_REQUIRED=false для локальной разработки)"
}

pip install -r requirements.txt -q
Write-Host "[OK] Python зависимости" -ForegroundColor Green

# Frontend
if (-not $SkipFrontend) {
    Set-Location "$Root\frontend"
    npm install --silent
    Write-Host "[OK] npm зависимости" -ForegroundColor Green
}

Set-Location $Root
Write-Host ""
Write-Host "Запуск (2 терминала):" -ForegroundColor Yellow
Write-Host "  1) cd backend; uvicorn app.main:app --reload --port 8000"
Write-Host "  2) cd frontend; npm run dev"
if ($WithWorker) {
    Write-Host "  3) cd backend; celery -A app.tasks.celery_app worker --loglevel=info --pool=solo"
    Write-Host "     (на Windows обязателен --pool=solo)"
}
Write-Host ""
Write-Host "Docker (облако/прод):" -ForegroundColor Yellow
Write-Host "  docker compose up -d"
Write-Host ""
Write-Host "Пользователи по умолчанию (при AUTH_REQUIRED=true): admin/admin, operator/operator, viewer/viewer"
