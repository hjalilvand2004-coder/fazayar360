@echo off
chcp 65001 >nul
title Fazayar360 - Portable
setlocal
set "ROOT=%~dp0"
set "PY=%ROOT%python-embed\python.exe"
set "PGBIN=%ROOT%pgsql\bin"
set "PGDATA=%ROOT%data\pgdata"
set "PGPORT=8098"
set "APPPORT=8095"
set "PGPASSWORD=fazayar"

if not exist "%PY%" ( echo python-embed not found & pause & exit /b 1 )
if not exist "%PGBIN%\initdb.exe" ( echo pgsql binaries not found & pause & exit /b 1 )

if not exist "%ROOT%data" mkdir "%ROOT%data"

if not exist "%PGDATA%\PG_VERSION" (
  echo [1/3] Initialising PostgreSQL data directory ^(first run^)...
  echo fazayar>"%ROOT%data\pwfile.txt"
  "%PGBIN%\initdb.exe" -D "%PGDATA%" -U fazayar --pwfile="%ROOT%data\pwfile.txt" -E UTF8 -A scram-sha-256 > "%ROOT%data\initdb.log" 2>&1
  del "%ROOT%data\pwfile.txt" 2>nul
)

echo [2/3] Starting PostgreSQL on port %PGPORT%...
"%PGBIN%\pg_ctl.exe" -D "%PGDATA%" -l "%ROOT%data\pg.log" -o "-p %PGPORT%" start

set /a WAIT=0
:waitpg
"%PGBIN%\pg_isready.exe" -h 127.0.0.1 -p %PGPORT% >nul 2>&1
if %errorlevel%==0 goto pgready
timeout /t 1 >nul
set /a WAIT+=1
if %WAIT% LSS 30 goto waitpg
echo PostgreSQL did not become ready - see data\pg.log
pause & exit /b 1

:pgready
"%PGBIN%\psql.exe" -h 127.0.0.1 -p %PGPORT% -U fazayar -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='fazayar'" | findstr "1" >nul
if %errorlevel% NEQ 0 "%PGBIN%\createdb.exe" -h 127.0.0.1 -p %PGPORT% -U fazayar fazayar

echo [3/3] Starting Fazayar360 on port %APPPORT% ...
set "FAZAYAR_DATABASE_URL=postgresql+psycopg2://fazayar:fazayar@127.0.0.1:%PGPORT%/fazayar"
set "FAZAYAR_DIST_DIR=%ROOT%app\frontend-dist"
set "FAZAYAR_UPLOAD_DIR=%ROOT%data\uploads"
set "FAZAYAR_JWT_SECRET=change-me-in-production"

start "" cmd /c "timeout /t 5 >nul & start http://localhost:%APPPORT%"
cd /d "%ROOT%app"
"%PY%" -m uvicorn app.main:app --host 0.0.0.0 --port %APPPORT%
pause
endlocal
