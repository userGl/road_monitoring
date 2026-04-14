#!/usr/bin/env pwsh
param()

$ErrorActionPreference = 'Stop'


function Select-Stream {
    Write-Host "Выбери поток для просмотра:" -ForegroundColor Cyan
    Write-Host "  1) live    (rtsp://127.0.0.1:8554/live)"
    Write-Host "  2) preview (rtsp://127.0.0.1:8554/preview)"
    Write-Host "  0) выход"
    $choice = Read-Host "Ваш выбор [0-2]"
    return $choice
}

# Проверка, что mpv доступен
$mpv = Get-Command "mpv.exe" -ErrorAction SilentlyContinue
if (-not $mpv) {
    Write-Host "mpv.exe не найден в PATH. Добавь папку mpv в PATH или укажи полный путь в скрипте." -ForegroundColor Red
    exit 1
}

$choice = Select-Stream

switch ($choice) {
    '1' {
        $rtspUrl = 'rtsp://127.0.0.1:8554/live'
    }
    '2' {
        $rtspUrl = 'rtsp://127.0.0.1:8554/preview'
    }
    '0' {
        Write-Host "Выход."
        exit 0
    }
    default {
        Write-Host "Неизвестный выбор: $choice" -ForegroundColor Red
        exit 1
    }
}

Write-Host "Открываю поток: $rtspUrl" -ForegroundColor Green

# mpv сам выберет подходящий backend
& $mpv.Source `
    "--hwdec=auto" `
    "--rtsp-transport=tcp" `
    "--title=$rtspUrl" `
    "$rtspUrl"