@echo off
setlocal EnableExtensions
chcp 65001 >nul
title video-promo 控制台
cd /d "%~dp0"

echo ========================================
echo   video-promo-pipeline 一键启动
echo   Web 面板: http://127.0.0.1:8766
echo   关闭本窗口即停止服务
echo ========================================
echo.

where python >nul 2>&1
if errorlevel 1 (
  echo [错误] 未找到 Python，请先安装 Python 3.10 或更高版本并加入 PATH
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo [首次运行] 正在创建虚拟环境并安装依赖，请稍候...
  powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0run.ps1" -Setup
  if errorlevel 1 (
    echo.
    echo [错误] 环境初始化失败，可手动执行: run.ps1 -Setup
    pause
    exit /b 1
  )
  echo [完成] 环境已就绪
  echo.
)

if not exist "config.yaml" (
  if exist "config.example.yaml" (
    copy /Y "config.example.yaml" "config.yaml" >nul
    echo [提示] 已从 config.example.yaml 生成 config.yaml
  )
)

if not exist "watch_in" mkdir "watch_in" >nul 2>&1

call ".venv\Scripts\activate.bat"
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1

echo [启动] 2 秒后自动打开浏览器...
start "" cmd /c "timeout /t 2 /nobreak >nul && start http://127.0.0.1:8766"

echo [启动] Web 服务运行中 ^(Ctrl+C 停止^)
echo.
python web_app.py
set "EXIT_CODE=%ERRORLEVEL%"

if not "%EXIT_CODE%"=="0" (
  echo.
  echo [错误] 服务异常退出，代码: %EXIT_CODE%
  echo 可尝试: run.ps1 -Preflight  检查 FFmpeg / LM Studio 等依赖
  pause
)

endlocal & exit /b %EXIT_CODE%
