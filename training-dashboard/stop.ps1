# Stop the Heatwave Training Dashboard (frees ports 8000 and 5173).
#   powershell -ExecutionPolicy Bypass -File training-dashboard\stop.ps1
foreach ($p in 8000, 5173) {
  $procs = Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue |
    Select-Object -ExpandProperty OwningProcess -Unique
  foreach ($id in $procs) { Stop-Process -Id $id -Force -ErrorAction SilentlyContinue }
  if ($procs) { Write-Host "stopped port $p (pid $($procs -join ', '))" } else { Write-Host "port $p already free" }
}
