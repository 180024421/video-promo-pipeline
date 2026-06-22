@echo off
REM 兼容旧入口，转发到 start.cmd
cd /d "%~dp0"
call "%~dp0start.cmd" %*
