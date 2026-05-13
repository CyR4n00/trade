@echo off

cd /d "%~dp0"

:: Activate Anaconda environment if it exists in the default user directory
if exist "%USERPROFILE%\anaconda3\Scripts\activate.bat" (
    call "%USERPROFILE%\anaconda3\Scripts\activate.bat"
) else if exist "C:\ProgramData\Anaconda3\Scripts\activate.bat" (
    call "C:\ProgramData\Anaconda3\Scripts\activate.bat"
)

python -m streamlit run app.py

pause
