$projectRoot = Split-Path $PSScriptRoot -Parent
$configPath = Join-Path $projectRoot "config.yaml"

if (-not (Test-Path $configPath)) {
    Write-Error "Config not found: $configPath"
    exit 1
}

$configText = Get-Content $configPath -Raw

$videoRel = [regex]::Match($configText, '(?m)^\s*video:\s*"?(.*?)"?\s*$').Groups[1].Value
$rtspPort = [regex]::Match($configText, '(?m)^\s*rtsp_port:\s*(\d+)\s*$').Groups[1].Value
$rtspPath = [regex]::Match($configText, '(?m)^\s*rtsp_path:\s*"?(.*?)"?\s*$').Groups[1].Value

if (-not $videoRel) {
    Write-Error "video not found in config.yaml"
    exit 1
}

if (-not $rtspPort) {
    $rtspPort = 8554
}

if (-not $rtspPath) {
    $rtspPath = "live"
}

$videoPath = Join-Path $projectRoot $videoRel
$videoPath = [System.IO.Path]::GetFullPath($videoPath)

$vlcPath = "C:\Program Files\VideoLAN\VLC\vlc.exe"

if (-not (Test-Path $vlcPath)) {
    Write-Error "VLC not found: $vlcPath"
    exit 1
}

if (-not (Test-Path $videoPath)) {
    Write-Error "Video file not found: $videoPath"
    exit 1
}

Write-Host "Starting VLC RTSP server..." -ForegroundColor Cyan
Write-Host "Video: $videoPath" -ForegroundColor Cyan
Write-Host "URL: rtsp://127.0.0.1:$rtspPort/$rtspPath" -ForegroundColor Cyan

& $vlcPath `
  --loop `
  $videoPath `
  ":sout=#gather:rtp{sdp=rtsp://:$rtspPort/$rtspPath}" `
  ":network-caching=500" `
  ":sout-all" `
  ":sout-keep"