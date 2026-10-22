@echo off
echo ============================================
echo   CFDT Mobilite - Installation
echo ============================================
echo.

REM Verifier Python
python --version >NUL 2>&1
if errorlevel 1 (
    echo [ERREUR] Python n'est pas installe sur cet ordinateur.
    echo.
    echo Telechargez Python 3.11 ici :
    echo https://www.python.org/downloads/
    echo.
    echo Cochez bien "Add Python to PATH" lors de l'installation.
    pause
    exit /b 1
)

python --version
echo.
echo Installation des modules requis...
echo.

python -m pip install --upgrade pip --quiet
python -m pip install -r "%~dp0requirements.txt" --quiet

if errorlevel 1 (
    echo.
    echo [ERREUR] L'installation a echoue.
    echo Verifiez votre connexion internet et relancez ce fichier.
    pause
    exit /b 1
)

echo.
echo ============================================
echo   Installation terminee !
echo   Lancez maintenant : lancer.bat
echo ============================================
pause
