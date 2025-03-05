@echo off
chcp 65001 > nul
setlocal enabledelayedexpansion
color 0A

:: Verifica daca ruleaza ca administrator
>nul 2>&1 "%SYSTEMROOT%\system32\cacls.exe" "%SYSTEMROOT%\system32\config\system"
IF %ERRORLEVEL% NEQ 0 (
    echo [91mATENTIE: Aplicatia necesita drepturi de administrator![0m
    echo [93mSe solicita drepturi de administrator...[0m
    
    :: Creeaza un script VBScript temporar pentru a obtine drepturi administrative
    echo Set objShell = CreateObject^("Shell.Application"^) > "%temp%\elevate.vbs"
    echo objShell.ShellExecute "cmd.exe", "/c cd /d ""%~dp0"" && ""%~f0""", "", "runas", 1 >> "%temp%\elevate.vbs"
    
    :: Ruleaza scriptul VBScript si iesi
    start "" "%temp%\elevate.vbs"
    del "%temp%\elevate.vbs"
    exit /b
)

:: Acum rulam ca administrator
cls
echo [92m======================================================[0m
echo [92m           OPTIMAD - RULEAZA CA ADMINISTRATOR         [0m
echo [92m======================================================[0m
echo.
echo [95mATENTIE: Aceasta aplicatie modifica data sistemului![0m
echo.
cd /d "%~dp0"

:: Seteaza calea catre mediul virtual si scriptul principal
set "VENV_PATH=%~dp0.venv"
set "ACTIVATE=%VENV_PATH%\Scripts\activate.bat"
set "MAIN_SCRIPT=%~dp0main.py"

:: Verifica daca mediul virtual exista, il creeaza daca este necesar
if not exist "%ACTIVATE%" (
    echo [96mSe creeaza mediul virtual...[0m
    python setup.py
    if not exist "%ACTIVATE%" (
        echo [91mEsec la crearea mediului virtual![0m
        pause
        exit /b 1
    )
)

:: Activeaza mediul virtual si ruleaza aplicatia
call "%ACTIVATE%"
echo [92mMediul virtual activat[0m
echo.
echo [96mSe executa aplicatia...[0m
echo [93mCapturile de ecran vor fi salvate in directoarele AAAA-LL-ZZ din acest director.[0m
echo.

python "%MAIN_SCRIPT%"

echo.
echo [92mAplicatia s-a incheiat.[0m
echo.
pause