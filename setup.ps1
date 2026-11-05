# One-time setup on Windows. Run from this folder:   .\setup.ps1
$ErrorActionPreference = "Stop"

Write-Host "1/4 Checking Python 3.12..." -ForegroundColor Cyan
py -3.12 --version
if ($LASTEXITCODE -ne 0) { Write-Host "Python 3.12 not found. Install it from python.org first." -ForegroundColor Red; exit 1 }

Write-Host "2/4 Creating virtual environment (.venv)..." -ForegroundColor Cyan
if (-not (Test-Path ".venv")) { py -3.12 -m venv .venv }

Write-Host "3/4 Installing packages (5-10 minutes the first time)..." -ForegroundColor Cyan
.\.venv\Scripts\python.exe -m pip install --upgrade pip --quiet
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

Write-Host "4/4 Running tests..." -ForegroundColor Cyan
.\.venv\Scripts\python.exe -m pytest -q

Write-Host ""
Write-Host "Done. Next:" -ForegroundColor Green
Write-Host "  1. notepad .env                 (paste your Groq key)"
Write-Host "  2. .venv\Scripts\Activate.ps1"
Write-Host "  3. streamlit run app.py"
