<#
Start DuuniScript automatically when you sign in to Windows (no administrator rights needed).

Creates a shortcut "DuuniScript.lnk" in your Startup folder that runs start_duuniscript.ps1
with -NoBrowser, so feeds, alert emails, backups and notifications run in the background; open
http://127.0.0.1:8080 (or double-click "Start DuuniScript.cmd") when you want the app.

Usage (PowerShell):  powershell -ExecutionPolicy Bypass -File scripts\install_autostart.ps1 [-Remove]
#>
param([switch]$Remove)

$startup = [Environment]::GetFolderPath("Startup")
$link = Join-Path $startup "DuuniScript.lnk"
if ($Remove) {
    if (Test-Path $link) { Remove-Item $link; Write-Host "Removed: DuuniScript no longer starts at sign-in." }
    else { Write-Host "DuuniScript was not set to start at sign-in." }
    return
}
$script = Join-Path $PSScriptRoot "start_duuniscript.ps1"
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($link)
$shortcut.TargetPath = "powershell.exe"
$shortcut.Arguments = "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$script`" -NoBrowser"
$shortcut.WorkingDirectory = Split-Path -Parent $PSScriptRoot
$shortcut.WindowStyle = 7  # minimised
$shortcut.Description = "Start DuuniScript in the background"
$shortcut.Save()
Write-Host "DuuniScript will start in the background when you sign in to Windows ($link)."
