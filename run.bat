@echo off
setlocal
cd /d "%~dp0"

set "PYTHON_EXE="
set "PYTHONW_EXE="

if exist ".venv\Scripts\python.exe" (
    set "PYTHON_EXE=.venv\Scripts\python.exe"
    if exist ".venv\Scripts\pythonw.exe" set "PYTHONW_EXE=.venv\Scripts\pythonw.exe"
) else if exist "venv\Scripts\python.exe" (
    set "PYTHON_EXE=venv\Scripts\python.exe"
    if exist "venv\Scripts\pythonw.exe" set "PYTHONW_EXE=venv\Scripts\pythonw.exe"
) else (
    where python >nul 2>&1
    if %errorlevel%==0 (
        set "PYTHON_EXE=python"
        where pythonw >nul 2>&1
        if %errorlevel%==0 set "PYTHONW_EXE=pythonw"
    ) else (
        where py >nul 2>&1
        if %errorlevel%==0 (
            set "PYTHON_EXE=py -3"
            set "PYTHONW_EXE=pyw -3"
        )
    )
)

if "%PYTHON_EXE%"=="" (
    echo [ERROR] Python tidak ditemukan. Silakan install Python terlebih dahulu.
    pause
    exit /b 1
)

%PYTHON_EXE% -c "import customtkinter, PIL, win32print" >nul 2>&1
if errorlevel 1 (
    echo [INFO] Menginstall dependencies dari requirements.txt...
    %PYTHON_EXE% -m pip install -r requirements.txt
    if errorlevel 1 (
        echo [ERROR] Gagal menginstall dependencies.
        pause
        exit /b 1
    )
)

if not "%PYTHONW_EXE%"=="" (
    start "" %PYTHONW_EXE% "%~dp0run.py"
) else (
    %PYTHON_EXE% "%~dp0run.py"
)

endlocal
