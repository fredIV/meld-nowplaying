$startup = [Environment]::GetFolderPath('Startup')
$link = Join-Path $startup 'meld-spotify.lnk'
if (Test-Path $link) { Remove-Item $link -Force; Write-Host "Removed $link" }
else { Write-Host "Nothing to remove - autostart was not installed." }
