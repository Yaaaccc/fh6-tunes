@echo off
setlocal
cd /d "%~dp0"
set "PY=%USERPROFILE%\.workbuddy\binaries\python\versions\3.13.12\python.exe"
if exist "%PY%" goto run
set "PY=python"
where python >nul 2>nul
if not errorlevel 1 goto run
goto nopy
:run
echo ==============================================
echo   地平线6 调校速查 - 手机访问（局域网）
echo ==============================================
echo.
echo   手机连上与本电脑同一个 WiFi，
echo   用手机浏览器打开下面显示的地址即可。
echo.
echo   本窗口保持开启，关掉即停止服务。
echo.
"%PY%" "scripts\serve.py"
echo.
echo 服务已停止。
pause
goto end
:nopy
echo [错误] 未找到 Python 运行时。
echo   请安装 Python 3, 或修改本文件里的 PY 变量。
pause
:end
