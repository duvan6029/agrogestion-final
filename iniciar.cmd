@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (set "PY=py -3") else (set "PY=python")
if not exist .venv\Scripts\python.exe (
  %PY% -m venv .venv
  if errorlevel 1 goto error
)
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto error
.venv\Scripts\python.exe semilla.py
if errorlevel 1 goto error
start "" http://127.0.0.1:5000
.venv\Scripts\python.exe app.py
pause
exit /b
:error
echo No fue posible iniciar. Instale Python 3.11 o superior y revise la conexion a Internet.
pause
exit /b 1
