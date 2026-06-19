#!/usr/bin/env pwsh
param()

$ErrorActionPreference = 'Stop'

$ScriptDir  = Split-Path -Parent $MyInvocation.MyCommand.Path
$ConfigPath = Join-Path $ScriptDir 'scripts_config.yaml'

if (-not (Test-Path $ConfigPath)) {
    Write-Host "Config not found: $ConfigPath" -ForegroundColor Red
    exit 1
}

function Get-ConfigValue {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Key
    )

    $pattern = '^[\s]*' + [regex]::Escape($Key) + ':'

    $line = Select-String -Path $ConfigPath -Pattern $pattern -ErrorAction SilentlyContinue |
        Select-Object -First 1

    if (-not $line) {
        return $null
    }

    $value = $line.Line -replace '^[^:]+:\s*', '' -replace '"', '' -replace '''', ''
    return $value.Trim()
}

$outputHost = Get-ConfigValue 'output_host'
$outputPort = Get-ConfigValue 'output_port'
$outputPath = Get-ConfigValue 'output_path'

if ([string]::IsNullOrWhiteSpace($outputHost)) {
    $outputHost = '127.0.0.1'
}

if ([string]::IsNullOrWhiteSpace($outputPort)) {
    $outputPort = '9554'
}

if ([string]::IsNullOrWhiteSpace($outputPath)) {
    $outputPath = 'processed'
}

$rtspUrl = "rtsp://{0}:{1}/{2}" -f $outputHost, $outputPort, $outputPath

$mpv = Get-Command "mpv.exe" -ErrorAction SilentlyContinue
if (-not $mpv) {
    Write-Host "mpv.exe не найден в PATH. Добавь папку mpv в PATH или укажи полный путь в скрипте." -ForegroundColor Red
    exit 1
}

Write-Host "Открываю поток: $rtspUrl" -ForegroundColor Green

& $mpv.Source `
    "--hwdec=auto" `
    "--rtsp-transport=tcp" `
    "--title=$rtspUrl" `
    "$rtspUrl"