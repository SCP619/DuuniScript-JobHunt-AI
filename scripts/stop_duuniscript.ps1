<#
Stops DuuniScript: only the processes listening on 127.0.0.1:8000 (the API, "-m app.main") and
:8080 (the frontend dev server, "vite") that belong to DuuniScript. Other programs are left alone.

Usage (PowerShell): powershell -ExecutionPolicy Bypass -File scripts\stop_duuniscript.ps1
#>
$ports = @{ 8000 = "app.main"; 8080 = "vite" }
foreach ($port in $ports.Keys) {
    $conn = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $conn) { Write-Host "Nothing running on port $port."; continue }
    $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$($conn.OwningProcess)"
    if ($proc.CommandLine -notlike "*$($ports[$port])*") {
        Write-Host "Port $port is used by another program ($($proc.Name)); left alone."
        continue
    }
    # Stop the server and the console window that started it.
    $parent = Get-CimInstance Win32_Process -Filter "ProcessId=$($proc.ParentProcessId)" -ErrorAction SilentlyContinue
    Stop-Process -Id $proc.ProcessId -Force -ErrorAction SilentlyContinue
    if ($parent -and ($parent.CommandLine -like "*$($ports[$port])*" -or $parent.CommandLine -like "*DuuniScript*")) {
        Stop-Process -Id $parent.ProcessId -Force -ErrorAction SilentlyContinue
    }
    Write-Host "Stopped DuuniScript on port $port."
}
