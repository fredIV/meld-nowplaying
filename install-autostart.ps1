$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$startup = [Environment]::GetFolderPath('Startup')
$link = Join-Path $startup 'meld-spotify.lnk'

$shell = New-Object -ComObject WScript.Shell
$sc = $shell.CreateShortcut($link)
$sc.TargetPath = 'wscript.exe'
$sc.Arguments = '"' + (Join-Path $here 'start-hidden.vbs') + '"'
$sc.WorkingDirectory = $here
$sc.Description = 'Now playing overlay for Meld Studio'
$sc.Save()

Write-Host "Installed. meld-spotify will start with Windows."
Write-Host "Shortcut: $link"
