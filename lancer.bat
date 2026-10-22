@echo off
echo ============================================
echo   CFDT Mobilite - Demarrage
echo ============================================
echo.
echo Ouverture dans votre navigateur...
echo (Fermez cette fenetre pour arreter l'application)
echo.

REM Ouvrir le navigateur apres 2 secondes (le temps que Flask demarre)
start /b "" cmd /c "timeout /t 2 >NUL && start http://localhost:5000"

REM Pas de fichiers __pycache__ (evite les conflits de synchro OneDrive)
set PYTHONDONTWRITEBYTECODE=1

REM Lancer Flask
python "%~dp0app.py"

if errorlevel 1 (
    echo.
    echo [ERREUR] L'application n'a pas pu demarrer.
    echo Verifiez que Python est installe (installer.bat).
    pause
)
