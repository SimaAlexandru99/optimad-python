# Optimad

Optimad este o aplicatie desktop Windows care face capturi automate de ecran si modifica temporar data sistemului pentru a simula activitate pe zile consecutive. Aplicatia trebuie rulata cu drepturi de administrator.

## Cerinte

- Windows 10 sau mai nou
- Python 3.12 sau mai nou
- Drepturi de administrator pentru modificarea datei sistemului
- Minimum 500 MB spatiu liber pe disc

## Instalare

1. Creeaza sau recreeaza mediul virtual:

```powershell
python setup.py
```

2. Activeaza mediul virtual:

```powershell
.venv\Scripts\activate
```

3. Ruleaza aplicatia:

```powershell
.venv\Scripts\python.exe main.py
```

4. Pentru rulare elevata foloseste:

```powershell
run_admin.bat
```

## Comportament principal

- Capturile sunt salvate in directoare `YYYY-MM-DD\HH-MM-SS.png`
- Aplicatia poate porni imediat, la o ora fixa sau zilnic la o ora fixa
- Focalizarea automata este disponibila pentru `desktop`, `zoom`, `teams` si `chrome`
- Data initiala a sistemului este capturata la pornirea procesului si restaurata explicit la final, inclusiv pe oprire sau eroare
- Tabul `Cursuri` permite import Excel intr-o baza SQLite locala (`optimad.db`) si listarea sesiunilor importate

## Import cursuri

- Format Excel compatibil cu `optimad-desktop`
- Sheet obligatoriu: `Grafic cursuri`
- Sheet optional pentru linkuri: `Link-uri zoom`
- Fiecare import nou inlocuieste sesiunile existente din baza locala

## Teste

Ruleaza testele din mediul virtual:

```powershell
.venv\Scripts\python.exe -m pytest tests\unit
```

## Observatii

- `schedule_config.json` si `themeconfig.json` sunt fisiere de stare locala si nu ar trebui tratate ca fisiere de distributie
- Directorul `logs\` si directoarele de capturi sunt artefacte runtime
