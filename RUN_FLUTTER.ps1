# Run Flutter client - run AFTER the backend is started
# Usage: .\RUN_FLUTTER.ps1
# Requires Flutter SDK installed and in PATH (or pass -FlutterSdk)

param(
    [string]$ApiOrigin = 'http://127.0.0.1:8000',
    [string]$FlutterSdk = ''
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

if ($FlutterSdk) {
    $flutterExe = Join-Path $FlutterSdk 'bin\flutter.bat'
} else {
    $command = Get-Command flutter -ErrorAction SilentlyContinue
    if (-not $command) {
        throw "Flutter not found. Install Flutter SDK or pass -FlutterSdk 'C:\path\to\flutter'"
    }
    $flutterExe = $command.Source
}

Write-Host "Starting Flutter app (API: $ApiOrigin)..." -ForegroundColor Cyan

Push-Location (Join-Path $projectRoot 'app')
try {
    & $flutterExe run --dart-define="API_ORIGIN=$ApiOrigin"
} finally {
    Pop-Location
}
