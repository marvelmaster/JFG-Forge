@echo off
setlocal
cd /d "%~dp0"

set "VENV_PYTHON=%CD%\.venv\Scripts\python.exe"
set "DEPS_MARKER=%CD%\.venv\.jfg_forge_deps"

if not exist "%VENV_PYTHON%" (
    echo Creating the Python environment ^(first start only^)...
    py -3 -m venv .venv 2>nul
    if not exist "%VENV_PYTHON%" python -m venv .venv
)

if not exist "%VENV_PYTHON%" (
    echo.
    echo ERROR: Python 3.12 or newer was not found.
    echo Install it from https://www.python.org/downloads/ and tick "Add python.exe to PATH".
    pause
    exit /b 1
)

"%VENV_PYTHON%" -c "import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)"
if errorlevel 1 (
    echo.
    echo ERROR: JFG Forge needs Python 3.12 or newer.
    echo Delete the .venv folder, install a newer Python, and start again.
    pause
    exit /b 1
)

if not exist "%DEPS_MARKER%" (
    echo Installing requirements ^(first start only^)...
    "%VENV_PYTHON%" -m pip install --upgrade pip
    "%VENV_PYTHON%" -m pip install -r requirements.txt
    if errorlevel 1 (
        echo.
        echo ERROR: Installing the requirements failed. Check your internet connection.
        pause
        exit /b 1
    )
    echo installed> "%DEPS_MARKER%"
)

"%VENV_PYTHON%" -m jfg_forge %*
if errorlevel 1 (
    echo.
    echo JFG Forge stopped with an error. See the messages above.
    pause
    exit /b 1
)
exit /b 0
