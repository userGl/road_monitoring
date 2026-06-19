$ErrorActionPreference = 'Stop'

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$AppDir = Resolve-Path (Join-Path $ScriptDir '..')
$Main = Join-Path $AppDir 'main.py'
$PythonExe = Join-Path $AppDir '.venv\Scripts\python.exe'

if (-not (Test-Path $Main)) {
    Write-Host "Не найден main.py: $Main"
    exit 1
}

if (-not (Test-Path $PythonExe)) {
    Write-Host "Не найден python в venv: $PythonExe"
    Write-Host "Создай/настрой .venv и установи зависимости."
    exit 1
}

Set-Location $AppDir
& $PythonExe $Main @args
exit $LASTEXITCODE