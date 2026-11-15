<#
Adds "DuuniScript" and "Stop DuuniScript" shortcuts to your Desktop and Start menu (no
administrator rights needed). "DuuniScript" starts the app (if it is not running) and opens it
in your browser; "Stop DuuniScript" stops it.

Usage (PowerShell):  powershell -ExecutionPolicy Bypass -File scripts\install_shortcuts.ps1 [-Remove]
#>
param([switch]$Remove)

$repo = Split-Path -Parent $PSScriptRoot
$places = @(
    [Environment]::GetFolderPath("Desktop"),
    (Join-Path ([Environment]::GetFolderPath("Programs")) "DuuniScript")
)
$items = @(
    @{ Name = "DuuniScript"; Script = "start_duuniscript.ps1"; Style = 7; Text = "Start DuuniScript and open it" },
    @{ Name = "Stop DuuniScript"; Script = "stop_duuniscript.ps1"; Style = 1; Text = "Stop DuuniScript" }
)

if ($Remove) {
    foreach ($place in $places) {
        foreach ($item in $items) { Remove-Item (Join-Path $place "$($item.Name).lnk") -ErrorAction SilentlyContinue }
    }
    Remove-Item $places[1] -ErrorAction SilentlyContinue
    Write-Host "DuuniScript shortcuts removed."
    return
}

$shell = New-Object -ComObject WScript.Shell
$icon = Join-Path $repo "scripts\duuniscript.ico"
foreach ($place in $places) {
    New-Item -ItemType Directory -Force $place | Out-Null
    foreach ($item in $items) {
        $shortcut = $shell.CreateShortcut((Join-Path $place "$($item.Name).lnk"))
        $shortcut.TargetPath = "powershell.exe"
        $shortcut.Arguments = "-NoProfile -ExecutionPolicy Bypass -File `"$(Join-Path $PSScriptRoot $item.Script)`""
        $shortcut.WorkingDirectory = $repo
        $shortcut.WindowStyle = $item.Style
        $shortcut.Description = $item.Text
        if (Test-Path $icon) { $shortcut.IconLocation = $icon }
        $shortcut.Save()
    }
}
Write-Host "Added 'DuuniScript' and 'Stop DuuniScript' to your Desktop and Start menu."
