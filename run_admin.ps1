# Ensure running as administrator
if (-NOT ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")) {
    Write-Host "Requesting administrative privileges..."
    Start-Process powershell -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`"" -Verb RunAs
    Exit
}

# Set execution policy for this process
try {
    Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
}
catch {
    Write-Warning "Failed to set execution policy: $_"
}

# Activate virtual environment and run the application
$venvPath = Join-Path $PSScriptRoot ".venv\Scripts\activate.ps1"

if (Test-Path $venvPath) {
    . $venvPath
    Write-Host "Virtual environment activated"
    python $mainScript
}
else {
    Write-Host "Virtual environment not found. Running setup..."
    python setup.py
    if (Test-Path $venvPath) {
        . $venvPath
        python $mainScript
    } else {
        Write-Host "Failed to create virtual environment. Please check for errors."
    }
}

Read-Host -Prompt "Press Enter to exit"