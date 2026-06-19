# start_mediamtx_rtsp.ps1
# для запуска mediamtx в Docker и публикации RTSP потока
# необходимы docker и ffmpeg в PATH

$ErrorActionPreference = 'Stop'

# Определение корня проекта
$ScriptDir   = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Resolve-Path (Join-Path $ScriptDir '..')
$ConfigPath  = Join-Path $ScriptDir 'scripts_config.yaml'

Write-Host "ScriptDir:   $ScriptDir"
Write-Host "ProjectRoot: $ProjectRoot"
Write-Host "ConfigPath:  $ConfigPath"

if (-not (Test-Path $ConfigPath)) {
    Write-Host "Config not found: $ConfigPath"
    exit 1
}

# --- Чтение scripts_config.yaml ---

$videoLine = Select-String -Path $ConfigPath -Pattern '^[\s]*video:' -ErrorAction SilentlyContinue |
    Select-Object -First 1

if (-not $videoLine) {
    Write-Host "video not found in scripts_config.yaml"
    exit 1
}

$videoRel = $videoLine.Line -replace '^[^:]+:\s*', '' -replace '"', '' -replace '''', ''
$videoRel = $videoRel.Trim()

$simHostLine = Select-String -Path $ConfigPath -Pattern '^[\s]*simulator_host:' -ErrorAction SilentlyContinue |
    Select-Object -First 1

if ($simHostLine) {
    $simulatorHost = $simHostLine.Line -replace '^[^:]+:\s*', '' -replace '"', '' -replace '''', ''
    $simulatorHost = $simulatorHost.Trim()
} else {
    $simulatorHost = '127.0.0.1'
}

$simPortLine = Select-String -Path $ConfigPath -Pattern '^[\s]*simulator_port:' -ErrorAction SilentlyContinue |
    Select-Object -First 1

if ($simPortLine) {
    $simulatorPort = $simPortLine.Line -replace '^[^:]+:\s*', '' -replace '"', '' -replace '''', ''
    $simulatorPort = $simulatorPort.Trim()
} else {
    $simulatorPort = '8554'
}

$simPathLine = Select-String -Path $ConfigPath -Pattern '^[\s]*simulator_path:' -ErrorAction SilentlyContinue |
    Select-Object -First 1

if ($simPathLine) {
    $simulatorPath = $simPathLine.Line -replace '^[^:]+:\s*', '' -replace '"', '' -replace '''', ''
    $simulatorPath = $simulatorPath.Trim()
} else {
    $simulatorPath = 'live'
}

if ([string]::IsNullOrWhiteSpace($videoRel)) {
    Write-Host "video not found in scripts_config.yaml"
    exit 1
}

# --- Проверка наличия файла видео ---

$videoPath = Join-Path $ProjectRoot $videoRel
if (-not (Test-Path $videoPath)) {
    Write-Host "Video file not found: $videoPath"
    exit 1
}

# --- Проверка наличия docker и ffmpeg в PATH ---

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "Docker not found in PATH"
    exit 1
}

if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
    Write-Host "ffmpeg not found in PATH"
    exit 1
}

function Test-DockerAvailable {
    $prevEap = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        docker info 1>$null 2>$null
        return ($LASTEXITCODE -eq 0)
    } finally {
        $ErrorActionPreference = $prevEap
    }
}

# --- Проверка, что Docker доступен ---

if (-not (Test-DockerAvailable)) {
    Write-Host "Запустите Docker Desktop и повторите попытку" -ForegroundColor Yellow
    Read-Host "Нажмите Enter, чтобы закрыть окно"
    exit 0
}

# --- Обработчик выхода ---

function Cleanup {
    Write-Host ""
    Write-Host "Stopping streamer..."
    try {
        if (Test-DockerAvailable) {
            docker stop mediamtx 2>$null | Out-Null
        }
    } catch {
        # игнорируем
    }
}

$null = Register-EngineEvent -SourceIdentifier PowerShell.Exiting -Action { Cleanup }

# --- Запуск MediaMTX в Docker ---

$rtspUrl = "rtsp://{0}:{1}/{2}" -f $simulatorHost, $simulatorPort, $simulatorPath

$mediamtxRunning = docker ps --format '{{.Names}}' 2>$null | Where-Object { $_ -eq 'mediamtx' }

if ($mediamtxRunning) {
    Write-Host "MediaMTX is already running in Docker"
} else {
    Write-Host "Starting MediaMTX in Docker..."
    docker run -d --rm `
      --name mediamtx `
      -e MTX_PROTOCOLS=tcp `
      -p ${simulatorPort}:8554 `
      -p 1935:1935 `
      -p 8888:8888 `
      -p 8889:8889 `
      -p 8890:8890/udp `
      -p 8189:8189/udp `
      bluenviron/mediamtx:latest | Out-Null
}

Write-Host "Waiting for RTSP server on $rtspUrl ..."
Start-Sleep -Seconds 2

Write-Host "Publishing file: $videoPath"
Write-Host "RTSP URL: $rtspUrl"

ffmpeg `
    -loglevel info `
    -re `
    -stream_loop -1 `
    -i "$videoPath" `
    -an `
    -c:v copy `
    -rtsp_transport tcp `
    -f rtsp `
    "$rtspUrl"