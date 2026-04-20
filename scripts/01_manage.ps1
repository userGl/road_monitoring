$ErrorActionPreference = 'Stop'

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$AppDir = Resolve-Path (Join-Path $ScriptDir '..')
$Manager = Join-Path $AppDir 'scripts\manage.py'
$PythonExe = Join-Path $AppDir '.venv\Scripts\python.exe'

if (-not (Test-Path $Manager)) {
    Write-Host "Не найден manage.py: $Manager"
    exit 1
}

if (-not (Test-Path $PythonExe)) {
    Write-Host "Не найден python в venv: $PythonExe"
    Write-Host "Создай/настрой .venv и установи зависимости."
    exit 1
}

& $PythonExe $Manager @args
exit $LASTEXITCODE
