$targets = Get-CimInstance Win32_Process -Filter "Name='python.exe' or Name='pythonw.exe'" |
    Where-Object { $_.CommandLine -like '*server.py*' -or $_.CommandLine -like '*meld-spotify*' }
if ($targets) {
    $targets | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
    Write-Host "Stopped $($targets.Count) overlay process(es)."
} else {
    Write-Host "Nothing to stop."
}
