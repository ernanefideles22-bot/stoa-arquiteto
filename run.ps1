# STOA Civil - Script de execucao
Set-Location $PSScriptRoot

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "ATENCAO: Configure OPENAI_API_KEY no arquivo .env antes de continuar." -ForegroundColor Yellow
    notepad .env
    exit
}

# Criar pasta do banco fora do OneDrive
$dbDir = "C:\stoa-civil"
if (-not (Test-Path $dbDir)) {
    New-Item -ItemType Directory -Path $dbDir | Out-Null
    Write-Host "Pasta do banco criada: $dbDir" -ForegroundColor Cyan
}

if (-not (Test-Path ".venv")) {
    Write-Host "Criando ambiente virtual..." -ForegroundColor Cyan
    python -m venv .venv
}

& ".venv\Scripts\Activate.ps1"
pip install -r requirements.txt -q

$port = if ($env:PORT) { $env:PORT } else { "8100" }
Write-Host ""
Write-Host "STOA Civil em http://localhost:$port" -ForegroundColor Green
Write-Host "Pressione Ctrl+C para parar" -ForegroundColor Gray
Write-Host ""
Start-Process "http://localhost:$port"
python -m uvicorn backend.main:app --reload --port $port --host 0.0.0.0
