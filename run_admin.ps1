# Asigura-te ca rulam ca administrator cu directorul de lucru corect
$OutputEncoding = [console]::OutputEncoding = [System.Text.Encoding]::UTF8

$currentPath = $MyInvocation.MyCommand.Path
$currentDir = Split-Path -Parent $currentPath

# Defineste o functie pentru a reporni scriptul ca administrator
function Restart-ScriptAsAdmin {
    if (-NOT ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")) {
        Write-Host "Se solicita drepturi de administrator..." -ForegroundColor Yellow
        $arguments = "-NoProfile -ExecutionPolicy Bypass -File `"$currentPath`""
        Start-Process powershell -Verb RunAs -ArgumentList $arguments
        exit
    }
}

# Apeleaza functia pentru a verifica/reporni ca administrator
Restart-ScriptAsAdmin

# Acum rulam ca administrator, setam directorul de lucru
Set-Location -Path $currentDir
Write-Host "Ruleaza cu drepturi de administrator" -ForegroundColor Green
Write-Host "ATENTIE: Aplicatia necesita drepturi de administrator pentru a functiona corect!" -ForegroundColor Magenta

# Defineste caile
$venvPath = Join-Path -Path $currentDir -ChildPath ".venv\Scripts\activate.ps1"
$mainScript = Join-Path -Path $currentDir -ChildPath "main.py"
$setupScript = Join-Path -Path $currentDir -ChildPath "setup.py"

# Verifica daca mediul virtual exista, il creeaza daca e necesar
if (-Not (Test-Path $venvPath)) {
    Write-Host "Se creeaza mediul virtual..." -ForegroundColor Cyan
    & python $setupScript

    if (-Not (Test-Path $venvPath)) {
        Write-Host "Esec la crearea mediului virtual!" -ForegroundColor Red
        Read-Host -Prompt "Apasa Enter pentru a iesi"
        exit 1
    }
}

# Activeaza mediul virtual
try {
    . $venvPath
    Write-Host "Mediul virtual activat" -ForegroundColor Green
}
catch {
    Write-Host "Eroare la activarea mediului virtual: $_" -ForegroundColor Red
    Read-Host -Prompt "Apasa Enter pentru a iesi"
    exit 1
}

# Ruleaza aplicatia
Write-Host "Se executa aplicatia..." -ForegroundColor Cyan
Write-Host "Capturile de ecran vor fi salvate in directoarele AAAA-LL-ZZ din acest director." -ForegroundColor Yellow
Write-Host ""

try {
    & python $mainScript
}
catch {
    Write-Host "Eroare la rularea aplicatiei: $_" -ForegroundColor Red
}

Write-Host ""
Write-Host "Aplicatia s-a incheiat." -ForegroundColor Green
Read-Host -Prompt "Apasa Enter pentru a iesi"
