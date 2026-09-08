@echo off
cd /d "%~dp0"
gh release delete v0.1.1 --yes --cleanup-tag > _redraft.log 2>&1
echo done >> _redraft.log
