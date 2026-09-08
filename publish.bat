@echo off
setlocal
cd /d "%~dp0"

set REPO=fredIV/meld-nowplaying
set TAG=v0.1.1
set ZIP=meld-nowplaying-%TAG%-windows.zip

echo Publishing %REPO% %TAG% ...
echo.

where gh >nul 2>&1
if errorlevel 1 goto nogh

gh auth status >nul 2>&1
if errorlevel 1 (
  echo You are not signed in to the GitHub CLI. Run:  gh auth login
  pause & exit /b 1
)

if not exist "%ZIP%" (
  echo %ZIP% is missing - run build-exe.bat first, then zip dist\meld-nowplaying.exe.
  pause & exit /b 1
)

REM --- push whatever is committed -------------------------------------------
git remote get-url origin >nul 2>&1
if errorlevel 1 (
  gh repo create %REPO% --public --source=. --remote=origin --push ^
     --description "Now playing overlay for Meld Studio - Spotify, YouTube, anything. No API keys." || (
    echo Could not create the repository. & pause & exit /b 1
  )
) else (
  git push origin main || (echo Push failed. & pause & exit /b 1)
)

REM --- checksum so people can verify the download ---------------------------
for /f "skip=1 delims=" %%h in ('certutil -hashfile "%ZIP%" SHA256') do (
  if not defined HASH set "HASH=%%h"
)
set "HASH=%HASH: =%"
echo SHA-256: %HASH%

copy /y RELEASE_NOTES.md _notes.md >nul
>> _notes.md echo.
>> _notes.md echo ---
>> _notes.md echo.
>> _notes.md echo ### Verify your download
>> _notes.md echo.
>> _notes.md echo SHA-256 of `%ZIP%`:
>> _notes.md echo.
>> _notes.md echo ```
>> _notes.md echo %HASH%
>> _notes.md echo ```
>> _notes.md echo.
>> _notes.md echo Check it yourself with:
>> _notes.md echo.
>> _notes.md echo ```
>> _notes.md echo certutil -hashfile %ZIP% SHA256
>> _notes.md echo ```

REM --- create the draft, or refresh it if it already exists ------------------
gh release view %TAG% >nul 2>&1
if errorlevel 1 (
  gh release create %TAG% "%ZIP%" --draft --title "meld-nowplaying %TAG%" --notes-file _notes.md || (
    echo Could not create the draft release. & del _notes.md & pause & exit /b 1
  )
  echo Draft release created.
) else (
  gh release edit %TAG% --notes-file _notes.md >nul || (echo Could not update the notes. & del _notes.md & pause & exit /b 1)
  gh release upload %TAG% "%ZIP%" --clobber || (echo Could not upload the asset. & del _notes.md & pause & exit /b 1)
  echo Existing release refreshed.
)
del _notes.md

echo.
echo Done - the release is a DRAFT. Review it and hit publish:
gh release view %TAG% --web
pause
exit /b 0

:nogh
echo The GitHub CLI (gh) is not installed, so this script cannot publish for you.
echo Install it from https://cli.github.com and run this again.
pause
exit /b 1
