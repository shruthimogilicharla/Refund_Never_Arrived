@echo off
cd /d "%~dp0"
echo.
echo === Push Refund_Never_Arrived to GitHub ===
echo.
set /p GHEMAIL=Type the email you use on GitHub and press Enter:
git config user.name "Shruthi Mogilicharla"
git config user.email "%GHEMAIL%"
git commit --amend --reset-author --no-edit -q
git branch -M main
git remote remove origin 2>nul
git remote add origin https://github.com/shruthimogilicharla/Refund_Never_Arrived.git
git push -u origin main --force
echo.
echo Done. Refresh https://github.com/shruthimogilicharla/Refund_Never_Arrived
pause
