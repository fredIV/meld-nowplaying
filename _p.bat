@echo off
cd /d "%~dp0"
git push origin main > _p.log 2>&1
