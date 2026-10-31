@echo off
cd /d "%~dp0"
echo.
echo ===== Refund Never Arrived - check it works =====
echo.

python --version >nul 2>&1
if errorlevel 1 (
  echo Python is not installed or not on PATH.
  echo Install it from https://www.python.org/downloads/ and tick "Add Python to PATH".
  pause
  exit /b
)
python --version

echo.
echo [1/5] Installing libraries...
python -m pip --version >nul 2>&1
if errorlevel 1 (
  echo pip is missing, installing it...
  python -m ensurepip --upgrade
)
python -m pip install -q --upgrade pip
python -m pip install -r requirements.txt
if errorlevel 1 (
  echo.
  echo Library install failed. Send a screenshot of the lines above.
  pause
  exit /b
)

echo.
echo [2/5] Solving the 24 sample complaints...
python code\main.py --sample

echo.
echo [3/5] Score on samples:
python code\evaluation\main.py --pred sample_predictions.csv --answers dataset\sample_output.csv --show-misses 5

echo.
echo [4/5] One complaint, step by step (R0002):
echo ------------------------------------------------------------
python code\main.py --explain R0002
echo ------------------------------------------------------------

echo.
echo [5/5] Solving all 300 complaints and running tests...
python code\main.py
python -m pytest -q

echo.
echo Opening the visual dashboard in your browser...
python code\dashboard.py

echo.
echo ===== Done. Open output.csv to see all 300 answers. =====
pause
