@echo off
REM 一键启动/停止/重启/查看 高考志愿专业推荐 前后端服务（Windows .bat 包装）
REM
REM 用法:
REM   scripts\dev.bat              双击 = start
REM   scripts\dev.bat start
REM   scripts\dev.bat stop
REM   scripts\dev.bat restart
REM   scripts\dev.bat status
REM
REM 实际逻辑在 dev.ps1，这里只是为了让双击和旧式 cmd 也能用。
REM 若 PowerShell 执行策略限制，脚本会用 -ExecutionPolicy Bypass 临时绕过（仅本进程）。

setlocal
set "ACTION=%~1"
if "%ACTION%"=="" set "ACTION=start"

set "SCRIPT_DIR=%~dp0"

powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%dev.ps1" "%ACTION%"
set "RC=%ERRORLEVEL%"

echo.
pause
exit /b %RC%
