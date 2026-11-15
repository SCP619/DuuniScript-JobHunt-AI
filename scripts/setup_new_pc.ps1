<#
Sets DuuniScript up on another Windows PC (no administrator rights needed).

Before running: install Git, Node.js LTS and uv (https://docs.astral.sh/uv/), and optionally
Ollama for local AI. Clone this repository (backend and frontend are both in it).

Usage (PowerShell, repository root):
    powershell -ExecutionPolicy Bypass -File scripts\setup_new_pc.ps1 `
        [-Backup <DuuniScript-backup-....zip>] [-GoogleClientFile <client_secret_....json>] [-Autostart]

-Backup            your data from the other PC (Settings > Backups, or %LOCALAPPDATA%\DuuniScript\backups).
                   Restored only into an empty data folder; nothing is overwritten.
-GoogleClientFile  the Google OAuth client file, if you use the Gmail connector. Copied into the
                   private data folder, never into the repository.
-Autostart         also start DuuniScript in the background at Windows sign-in.

Things that stay on each PC and must be done again in the app: connecting Gmail / UTU mail
(sign-in tokens live in Windows Credential Manager) and the IMAP mailbox password.
#>
param([string]$Backup, [string]$GoogleClientFile, [switch]$Autostart)

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
$frontend = Join-Path $repo "frontend"
$data = if ($env:APP_DATA_DIR) { $env:APP_DATA_DIR } else { Join-Path $env:LOCALAPPDATA "DuuniScript" }
$python = Join-Path $repo ".venv\Scripts\python.exe"

function Need([string]$cmd, [string]$what) {
    if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) { throw "$what is not installed (command '$cmd' not found)." }
}
Need git "Git"; Need npm "Node.js"; Need uv "uv"

Write-Host "1/6 Backend (Python environment and packages)..."
Push-Location $repo
try {
    if (-not (Test-Path $python)) { uv venv --python 3.11 .venv | Out-Host }
    uv pip install --python $python -e ".[dev]" | Out-Host
} finally { Pop-Location }

Write-Host "2/6 Frontend..."
Push-Location $frontend
try { npm install --no-fund --no-audit | Out-Host } finally { Pop-Location }

Write-Host "3/6 Settings (.env)..."
$envFile = Join-Path $repo ".env"
if (-not (Test-Path $envFile)) {
    "# Local settings for this computer. Never committed (see .gitignore)." | Set-Content -Encoding utf8 $envFile
}

Write-Host "4/6 Local AI (optional)..."
if (Get-Command ollama -ErrorAction SilentlyContinue) {
    ollama pull qwen2.5:7b | Out-Host
    ollama pull bge-m3 | Out-Host
    $lines = @(Get-Content $envFile | Where-Object { $_ -notmatch "^OLLAMA_(EMBED_)?MODEL=" }) + "OLLAMA_MODEL=qwen2.5:7b" + "OLLAMA_EMBED_MODEL=bge-m3"
    $lines | Set-Content -Encoding utf8 $envFile
} else {
    Write-Host "   Ollama not installed: skipped (the app works without it; install it later and run this again)."
}

Write-Host "5/6 Your data..."
if ($Backup) {
    & $python (Join-Path $repo "scripts\restore_backup.py") $Backup
    if ($LASTEXITCODE -ne 0) { throw "Restoring the backup failed (see above). Nothing was overwritten." }
} else {
    Write-Host "   No -Backup given: starting with an empty data folder."
}
# After the restore, which needs an empty data folder.
New-Item -ItemType Directory -Force $data | Out-Null
if ($GoogleClientFile) {
    $target = Join-Path $data "google_oauth_client.json"
    Copy-Item $GoogleClientFile $target -Force
    $lines = @(Get-Content $envFile | Where-Object { $_ -notmatch "^GOOGLE_OAUTH_CLIENT_FILE=" }) + "GOOGLE_OAUTH_CLIENT_FILE=$target"
    $lines | Set-Content -Encoding utf8 $envFile
}

Write-Host "6/6 Shortcuts..."
& (Join-Path $PSScriptRoot "install_shortcuts.ps1")
if ($Autostart) { & (Join-Path $PSScriptRoot "install_autostart.ps1") }

Write-Host ""
Write-Host "Done. Start DuuniScript from the Desktop shortcut. Then, in the app, reconnect Gmail / UTU mail if you use them."
