@echo off
cd /d "%~dp0"
echo ==========================================================
echo Starting GitHub Push to Choi-ai-study...
echo (If a GitHub Sign-in window pops up, click Sign in with your browser)
echo ==========================================================
"C:\Program Files\Git\cmd\git.exe" add .
"C:\Program Files\Git\cmd\git.exe" commit -m "Update project files"
"C:\Program Files\Git\cmd\git.exe" push -u origin main
echo.
echo ==========================================================
echo Done! Now run this in your phone Termux:
echo   git clone https://github.com/cdy6808-beep/Choi-ai-study.git
echo ==========================================================
pause
