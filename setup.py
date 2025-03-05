import subprocess
import sys
import os
from pathlib import Path

def setup_venv():
    venv_path = Path('.venv')
    
    # Create virtual environment
    print("Creating virtual environment...")
    subprocess.run([sys.executable, '-m', 'venv', '.venv'])
    
    # Determine the pip path
    if os.name == 'nt':  # Windows
        pip_path = venv_path / 'Scripts' / 'pip.exe'
    else:  # Unix-like
        pip_path = venv_path / 'bin' / 'pip'
    
    # Upgrade pip
    print("Upgrading pip...")
    subprocess.run([str(pip_path), 'install', '--upgrade', 'pip'])
    
    # Install requirements
    print("Installing requirements...")
    subprocess.run([str(pip_path), 'install', '-r', 'requirements.txt'])
    
    print("\nSetup complete! To activate the virtual environment:")
    if os.name == 'nt':
        print("Run: .venv\\Scripts\\activate")
    else:
        print("Run: source .venv/bin/activate")

if __name__ == '__main__':
    setup_venv()