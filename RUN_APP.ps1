# Run Anxin Companion - startup script
# Usage: .\RUN_APP.ps1

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "=== Anxin Companion Startup ===" -ForegroundColor Cyan

# Step 1: Create venv if it doesn't exist
$venvPython = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $venvPython)) {
    Write-Host "Creating virtual environment..." -ForegroundColor Yellow
    $sysPython = Get-Command python -ErrorAction SilentlyContinue
    if (-not $sysPython) {
        $managedPython = "C:\users\pc\.workbuddy-ai\binaries\python\versions\3.13.12\python.exe"
        if (Test-Path $managedPython) {
            & $managedPython -m venv (Join-Path $projectRoot '.venv')
        } else {
            throw "Python not found. Install Python 3.12+ or use the managed binary."
        }
    } else {
        & python -m venv (Join-Path $projectRoot '.venv')
    }
}

# Step 2: Install dependencies if needed
$sitePackages = Join-Path $projectRoot '.venv\Lib\site-packages'
$reqLock = Join-Path $projectRoot 'backend\requirements.lock.txt'
$reqHash = (Get-FileHash $reqLock -ErrorAction SilentlyContinue).Hash
$markerFile = Join-Path $sitePackages '.anxin_deps_installed'
$installedHash = Get-Content $markerFile -ErrorAction SilentlyContinue
if ($installedHash -ne $reqHash) {
    Write-Host "Installing backend dependencies..." -ForegroundColor Yellow
    & $venvPython -m pip install -r $reqLock
    $reqHash | Out-File $markerFile
}

# Step 3: Set AUTH_SECRET if not already set
if (-not $env:AUTH_SECRET) {
    $env:AUTH_SECRET = & $venvPython -c "import secrets; print(secrets.token_urlsafe(48))"
    Write-Host "Generated AUTH_SECRET for this session." -ForegroundColor Green
}

# Step 4: Start the backend
Write-Host "Starting backend on http://127.0.0.1:8000 ..." -ForegroundColor Green
Write-Host "API docs at http://127.0.0.1:8000/docs" -ForegroundColor DarkGray
Write-Host "Press Ctrl+C to stop." -ForegroundColor DarkGray
Write-Host ""

Push-Location (Join-Path $projectRoot 'backend')
try {
    & $venvPython -m uvicorn app.main:app --host 127.0.0.1 --port 8000
} finally {
    Pop-Location
}
