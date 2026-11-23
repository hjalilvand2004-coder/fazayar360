@echo off
chcp 65001 >nul
title Fazayar360 - Stop
setlocal
set "ROOT=%~dp0"
set "PGBIN=%ROOT%pgsql\bin"
set "PGDATA=%ROOT%data\pgdata"
echo Stopping Fazayar360 PostgreSQL...
"%PGBIN%\pg_ctl.exe" -D "%PGDATA%" -m fast stop
echo Done.
endlocal
