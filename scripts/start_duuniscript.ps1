<#
Starts DuuniScript on this computer and opens it in the browser.

- Backend (API) on http://127.0.0.1:8000, frontend on http://127.0.0.1:8080 (both only on this
  computer). Each runs in its own minimised window titled "DuuniScript backend" /
  "DuuniScript frontend"; close those windows, or run stop_duuniscript.ps1, to stop it.
- Anything already running on those ports is reused, not started twice.
- Frontend folder: -Frontend <path>, default: the "frontend" folder in this repository.

Usage (PowerShell): powershell -ExecutionPolicy Bypass -File scripts\start_duuniscript.ps1
#>
param(
    [string]$Frontend = (Join-Path (Split-Path -Parent $PSScriptRoot) "frontend"),
    [switch]$NoBrowser  # used when starting at Windows sign-in
)

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
$backend = Join-Path $repo "backend"
$python = Join-Path $repo ".venv\Scripts\python.exe"
$api = "http://127.0.0.1:8000"
$app = "http://127.0.0.1:8080"

function Test-Up([string]$url) {
    try { Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 $url | Out-Null; return $true } catch { return $false }
}

function Wait-Up([string]$url, [int]$seconds, [string]$what) {
    for ($i = 0; $i -lt $seconds; $i++) {
        if (Test-Up $url) { return }
        Start-Sleep -Seconds 1
    }
    throw "$what did not start within $seconds seconds. Look at the '$what' window for the error."
}

if (-not (Test-Path $python)) {
    throw "Python environment not found at $python. Install it first (docs\WINDOWS_SETUP.md)."
}
if (-not (Test-Path (Join-Path $Frontend "package.json"))) {
    throw "Frontend not found at $Frontend. Pass -Frontend <folder>."
}

Write-Host "DuuniScript: starting..."

if (Test-Up "$api/health") {
    Write-Host "  Backend already running."
} else {
    Start-Process cmd.exe -WorkingDirectory $backend -WindowStyle Minimized -ArgumentList @(
        "/k", "title DuuniScript backend && `"$python`" -m app.main"
    )
    Wait-Up "$api/health" 60 "DuuniScript backend"
    Write-Host "  Backend started."
}

if (Test-Up $app) {
    Write-Host "  Frontend already running."
} else {
    if (-not (Test-Path (Join-Path $Frontend "node_modules"))) {
        Write-Host "  Installing frontend packages (first start only)..."
        Push-Location $Frontend
        try { npm install --no-fund --no-audit | Out-Host } finally { Pop-Location }
    }
    Start-Process cmd.exe -WorkingDirectory $Frontend -WindowStyle Minimized -ArgumentList @(
        "/k",
        "title DuuniScript frontend && set `"VITE_USE_MOCKS=false`" && set `"VITE_API_BASE_URL=$api`" && npm run dev -- --port 8080 --strictPort --host 127.0.0.1"
    )
    Wait-Up $app 90 "DuuniScript frontend"
    Write-Host "  Frontend started."
}

# Local AI (optional): start Ollama if it is installed and not running.
$ollama = Join-Path $env:LOCALAPPDATA "Programs\Ollama\ollama.exe"
if ((Test-Path $ollama) -and -not (Test-Up "http://127.0.0.1:11434/api/version")) {
    Start-Process $ollama -ArgumentList "serve" -WindowStyle Hidden
}

if ($NoBrowser) {
    Write-Host "DuuniScript is running at $app"
} else {
    Start-Process $app
    Write-Host "DuuniScript is open at $app"
}
