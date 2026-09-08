@echo off
setlocal
cd /d "%~dp0"

set REPO=fredIV/meld-nowplaying
set TAG=v0.1.1

echo Publishing %REPO% ...
echo.

where gh >nul 2>&1
if errorlevel 1 goto nogh

gh auth status >nul 2>&1
if errorlevel 1 (
  echo You are not signed in to the GitHub CLI. Run:  gh auth login
  pause & exit /b 1
)

git remote get-url origin >nul 2>&1
if errorlevel 1 (
  gh repo create %REPO% --public --source=. --remote=origin --push ^
     --description "Now playing overlay for Meld Studio - Spotify, YouTube, anything. No API keys." || (
    echo Could not create the repository. & pause & exit /b 1
  )
) else (
  git push -u origin main || (echo Push failed. & pause & exit /b 1)
)

if not exist "dist\meld-nowplaying.exe" (
  echo dist\meld-nowplaying.exe is missing - run build-exe.bat first.
  pause & exit /b 1
)

gh release create %TAG% "meld-nowplaying-%TAG%-windows.zip" --draft ^
   --title "meld-nowplaying %TAG%" --notes-file RELEASE_NOTES.md || (
  echo Could not create the draft release. & pause & exit /b 1
)

echo.
echo Done. The repository is public and the release is a DRAFT - review it and hit
echo publish when you are happy:
gh release view %TAG% --web
pause
exit /b 0

:nogh
echo The GitHub CLI (gh) is not installed, so this script cannot create the repo
echo or the draft release for you.
echo.
echo Either install it from https://cli.github.com and run this again, or do it by hand:
echo   1. Create an empty public repo called meld-nowplaying at https://github.com/new
echo   2. git remote add origin https://github.com/%REPO%.git
echo   3. git push -u origin main
echo   4. Draft a release, attach dist\meld-nowplaying.exe, paste RELEASE_NOTES.md
pause
exit /b 1
