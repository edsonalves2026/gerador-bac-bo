# run.ps1
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Test-Path ".venv\Scripts\Activate.ps1")) {
    Write-Host "Criando venv..." -ForegroundColor Yellow
    python -m venv .venv
}
. .\.venv\Scripts\Activate.ps1

Write-Host "🔍 Validando sintaxe..." -ForegroundColor Cyan
Get-ChildItem bacbo\*.py | ForEach-Object {
    python -m py_compile $_.FullName
    if ($LASTEXITCODE -ne 0) { throw "Erro em $($_.Name)" }
}

Write-Host "🔍 Testando imports..." -ForegroundColor Cyan
python -c "from bacbo.worker import BacBoWorker; print('OK worker')"
if ($LASTEXITCODE -ne 0) { throw "Falha no import" }

Write-Host "🚀 Iniciando Streamlit..." -ForegroundColor Green
streamlit run app.py
