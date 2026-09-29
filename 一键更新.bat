@echo off
setlocal
cd /d "%~dp0"
echo ==========================================
echo   地平线6 调校速查 - 数据一键更新
echo ==========================================
echo.
set "PY=%USERPROFILE%\.workbuddy\binaries\python\versions\3.13.12\python.exe"
if exist "%PY%" goto run
set "PY=python"
where python >nul 2>nul
if not errorlevel 1 goto run
goto nopy
:run
"%PY%" "scripts\update.py"
if errorlevel 1 goto fail
echo.
echo [完成] 页面已刷新到最新数据, 正在打开...
start "" "FH6-调校速查.html"
goto end
:nopy
echo [错误] 未找到 Python 运行时。
echo   请安装 Python 3, 或修改本文件里的 PY 变量。
goto end
:fail
echo.
echo [错误] 更新未完成, 请查看上方提示。旧页面未被破坏。
:end
echo.
pause
