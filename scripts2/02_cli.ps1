$ErrorActionPreference = 'Stop'

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$AppDir    = Resolve-Path (Join-Path $ScriptDir '..')
$PythonExe = Join-Path $AppDir '.venv\Scripts\python.exe'

if (-not (Test-Path $PythonExe)) {
    Write-Host "Не найден python в venv: $PythonExe"
    Write-Host "Создай/настрой .venv и установи зависимости."
    exit 1
}

Push-Location $AppDir
try {
    & $PythonExe -m scripts2.cli.main @args
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
