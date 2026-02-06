# GraphRag local run check (Windows PowerShell)
# Run from repo root: .\scripts\run_local_check.ps1

$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
if (-not (Test-Path (Join-Path $root "src"))) { $root = (Get-Location).Path }
Set-Location $root

Write-Host "GraphRag local run check" -ForegroundColor Cyan
Write-Host ""

# 1. Python 3.10, 3.11, or 3.12 only (3.13 has no numpy wheels; would need C compiler to build)
$py = $null
foreach ($cmd in @("py", "python", "python3")) {
    try {
        $v = & $cmd -c "import sys; print(sys.version_info.major, sys.version_info.minor)" 2>$null
        if ($v) {
            $major, $minor = $v -split " "
            if ([int]$major -eq 3 -and [int]$minor -ge 10 -and [int]$minor -le 12) {
                $py = $cmd
                $ver = & $cmd --version 2>$null
                Write-Host "[OK] Python: $ver" -ForegroundColor Green
                break
            }
            if ([int]$major -eq 3 -and [int]$minor -eq 13) {
                Write-Host "[FAIL] Python 3.13 is not supported (numpy has no pre-built wheels; build would need a C compiler)." -ForegroundColor Red
                Write-Host "Use Python 3.10, 3.11, or 3.12. Example: install 3.12 from https://www.python.org/downloads/ then run:" -ForegroundColor Yellow
                Write-Host "  Remove-Item -Recurse -Force .venv -ErrorAction SilentlyContinue" -ForegroundColor White
                Write-Host "  py -3.12 -m venv .venv" -ForegroundColor White
                Write-Host "  .\.venv\Scripts\Activate.ps1" -ForegroundColor White
                Write-Host "  pip install -r requirements.txt" -ForegroundColor White
                exit 1
            }
        }
    } catch {}
}
if (-not $py) {
    Write-Host "[FAIL] Python 3.10, 3.11, or 3.12 not found (3.13 not supported). Install from https://www.python.org/" -ForegroundColor Red
    exit 1
}

# 2. .env
$envPath = Join-Path $root ".env"
if (-not (Test-Path $envPath)) {
    Write-Host "[WARN] .env not found. Copy .env.example to .env and set OPENAI_API_KEY, NEO4J_*, TELEGRAM_BOT_TOKEN." -ForegroundColor Yellow
} else {
    Write-Host "[OK] .env exists" -ForegroundColor Green
}

# 3. Venv and deps
$venv = Join-Path $root ".venv"
$venvPy = Join-Path $venv "Scripts\python.exe"
if (-not (Test-Path $venvPy)) {
    Write-Host "Creating venv..." -ForegroundColor Yellow
    & $py -m venv $venv
}
$pip = Join-Path $venv "Scripts\pip.exe"
Write-Host "Installing dependencies..." -ForegroundColor Yellow
& $venvPy -m pip install -q --upgrade pip
& $venvPy -m pip install -q -r (Join-Path $root "requirements.txt")
Write-Host "[OK] Dependencies installed" -ForegroundColor Green

# 4. Tests (no Neo4j/OpenAI needed; mocks used)
Write-Host "Running tests..." -ForegroundColor Yellow
$pytest = Join-Path $venv "Scripts\pytest.exe"
& $venvPy -m pytest (Join-Path $root "tests") -v --tb=short 2>&1 | Out-Host
if ($LASTEXITCODE -ne 0) {
    Write-Host "[FAIL] Some tests failed." -ForegroundColor Red
    exit 1
}
Write-Host "[OK] Tests passed" -ForegroundColor Green

Write-Host ""
Write-Host "Local run check passed. To run the app:" -ForegroundColor Cyan
Write-Host "  1. Ensure Neo4j is running (e.g. docker compose up -d neo4j) and .env has NEO4J_* and others." -ForegroundColor White
Write-Host "  2. Ingest data:  .\.venv\Scripts\python.exe -m src.data.ingestion" -ForegroundColor White
Write-Host "  3. Start bot:    .\.venv\Scripts\python.exe -m src.bot.telegram_bot" -ForegroundColor White
Write-Host "Or use Docker:    docker compose up -d" -ForegroundColor White
