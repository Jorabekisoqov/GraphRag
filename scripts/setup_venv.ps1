# Create .venv with Python 3.10, 3.11, or 3.12 (required; 3.13 not supported)
# Run from repo root: .\scripts\setup_venv.ps1

$root = Split-Path $PSScriptRoot -Parent
if (-not (Test-Path (Join-Path $root "src"))) { $root = (Get-Location).Path }
Set-Location $root

$venvPath = Join-Path $root ".venv"
$found = $null
foreach ($py in @("py -3.12", "py -3.11", "py -3.10", "python3.12", "python3.11", "python3.10")) {
    try {
        $v = & $py -c "import sys; print(sys.version_info.minor)" 2>$null
        if ($v -match '^(10|11|12)$') {
            $found = $py
            $ver = & $py --version 2>$null
            Write-Host "Using: $ver" -ForegroundColor Green
            break
        }
    } catch {}
}
if (-not $found) {
    Write-Host "Python 3.10, 3.11, or 3.12 not found. Python 3.13 is not supported." -ForegroundColor Red
    Write-Host "Install Python 3.12 from: https://www.python.org/downloads/release/python-3120/" -ForegroundColor Yellow
    Write-Host "Then run this script again." -ForegroundColor Yellow
    exit 1
}

if (Test-Path $venvPath) {
    Write-Host "Removing existing .venv ..." -ForegroundColor Yellow
    Remove-Item -Recurse -Force $venvPath
}
Write-Host "Creating .venv with $found ..." -ForegroundColor Cyan
$args = $found -split '\s+'
& $args[0] @($args[1..($args.Length-1)] + '-m', 'venv', $venvPath)
& (Join-Path $venvPath "Scripts\Activate.ps1")
Write-Host "Installing dependencies ..." -ForegroundColor Cyan
& (Join-Path $venvPath "Scripts\pip.exe") install -r (Join-Path $root "requirements.txt")
Write-Host "Done. Activate with: .\.venv\Scripts\Activate.ps1" -ForegroundColor Green
