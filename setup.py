import subprocess
import sys
import os
from pathlib import Path

def setup_venv():
    """Set up the virtual environment and install dependencies"""
    venv_path = Path('.venv')
    
    try:
        # Create virtual environment
        print("Se creeaza mediul virtual...")
        subprocess.run([sys.executable, '-m', 'venv', '.venv'], check=True)
        
        # Determine the pip path based on OS
        if os.name == 'nt':  # Windows
            pip_path = venv_path / 'Scripts' / 'pip.exe'
            python_path = venv_path / 'Scripts' / 'python.exe'
        else:  # Unix-like
            pip_path = venv_path / 'bin' / 'pip'
            python_path = venv_path / 'bin' / 'python'
        
        # Upgrade pip
        print("Se actualizeaza pip...")
        subprocess.run([str(pip_path), 'install', '--upgrade', 'pip'], check=True)
        
        # Install wheel for better package installation
        print("Se instaleaza wheel...")
        subprocess.run([str(pip_path), 'install', 'wheel'], check=True)
        
        # Install requirements
        print("Se instaleaza cerintele...")
        subprocess.run([str(pip_path), 'install', '-r', 'requirements.txt'], check=True)
        
        print("\nConfigurare completa!")
        print("Pentru a activa mediul virtual:")
        if os.name == 'nt':
            print("Rulati: .venv\\Scripts\\activate")
        else:
            print("Rulati: source .venv/bin/activate")
            
    except subprocess.CalledProcessError as e:
        print(f"Eroare la configurarea mediului virtual: {e}")
        print("Cod de iesire:", e.returncode)
        if e.output:
            print("Detalii:", e.output.decode())
        sys.exit(1)
    except Exception as e:
        print(f"Eroare neasteptata: {e}")
        sys.exit(1)

if __name__ == '__main__':
    if os.name != 'nt' and os.geteuid() == 0:
        print("AVERTISMENT: Nu rulati acest script ca root/administrator!")
        sys.exit(1)
    setup_venv()