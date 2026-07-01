# STOA Civil — Instalação
Set-Location $PSScriptRoot
Write-Host "🏗️  STOA Civil — Instalação" -ForegroundColor Cyan

# Verificar Python
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "❌ Python não encontrado. Instale Python 3.10+ em https://python.org" -ForegroundColor Red
    exit 1
}

# Criar .env
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "📝 Arquivo .env criado. Configure sua ANTHROPIC_API_KEY." -ForegroundColor Yellow
}

# Criar venv
Write-Host "📦 Criando ambiente virtual..." -ForegroundColor Cyan
python -m venv .venv

# Instalar dependências
Write-Host "📥 Instalando dependências..." -ForegroundColor Cyan
& ".venv\Scripts\Activate.ps1"
pip install --upgrade pip -q
pip install -r requirements.txt

Write-Host ""
Write-Host "✅ Instalação concluída!" -ForegroundColor Green
Write-Host ""
Write-Host "Próximo passo:" -ForegroundColor White
Write-Host "  1. Edite o arquivo .env e adicione sua ANTHROPIC_API_KEY" -ForegroundColor Gray
Write-Host "  2. Execute: .\run.ps1" -ForegroundColor Gray
Write-Host ""
