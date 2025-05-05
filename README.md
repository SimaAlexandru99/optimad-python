# Optimad - Aplicație pentru Capturi Automate de Ecran

## Prezentare generală

Optimad este o aplicație desktop dezvoltată în Python pentru realizarea automată a capturilor de ecran la intervale predefinite. Aplicația poate modifica temporar data sistemului pentru a simula activitate în zile consecutive și poate focaliza automat pe diverse aplicații precum Zoom, Microsoft Teams sau Google Chrome.

![Optimad Screenshot](resources/screenshot.png)

## Caracteristici principale

- **Capturi de ecran automate** la intervale configurabile
- **Modificarea datei sistemului** pentru simularea activității pe parcursul mai multor zile
- **Planificare flexibilă** - pornire imediată, la o oră specificată sau programare zilnică
- **Focalizare automată** pe diverse aplicații (Zoom, Teams, Chrome)
- **Interfață grafică intuitivă** cu teme personalizabile
- **Logging detaliat** pentru urmărirea activității și depanare

## Cerințe sistem

- Windows 10 sau mai recent
- Python 3.8 sau mai nou
- Drepturi de administrator (necesare pentru modificarea datei sistemului)
- Spațiu liber pe disc: minim 500 MB

## Instalare

### Metoda 1: Instalare automată

1. Clonați sau descărcați acest repository
2. Executați `setup.py` pentru a configura automat mediul virtual și a instala dependențele:

```bash
python setup.py
```

3. Activați mediul virtual:

```bash
# Windows
.venv\Scripts\activate

# Unix/Linux
source .venv/bin/activate
```

### Metoda 2: Instalare manuală

1. Clonați sau descărcați acest repository
2. Creați un mediu virtual:

```bash
python -m venv .venv
```

3. Activați mediul virtual:

```bash
# Windows
.venv\Scripts\activate

# Unix/Linux
source .venv/bin/activate
```

4. Instalați dependențele:

```bash
pip install -r requirements.txt
```

## Pornirea aplicației

Pentru a beneficia de toate funcționalitățile, aplicația trebuie rulată cu drepturi de administrator:

### Windows

Folosiți scriptul batch inclus:

```bash
run_admin.bat
```

Alternativ, puteți utiliza PowerShell:

```bash
powershell -Command "Start-Process python -ArgumentList 'main.py' -Verb RunAs"
```

## Utilizare

### Configurarea capturilor

1. **Ore de curs**: Introduceți numărul de ore pentru simulare (între 1 și 24)
2. **Număr de capturi de ecran**: Setați câte capturi doriți să realizați (între 1 și 60)
3. **Selectați aplicația**: Alegeți aplicația pe care doriți să o focalizați (Desktop, Zoom, Teams, Chrome)

### Opțiuni de pornire

- **Începe acum**: Pornește procesul imediat
- **Începe la ora specificată**: Pornește procesul la ora introdusă (format: HH:MM)
- **Rulează zilnic la ora specificată**: Programează rularea zilnică la ora stabilită

### Control

- **Pornește Procesul**: Inițiază procesul cu setările configurate
- **Oprește Procesul**: Oprește procesul în desfășurare
- **Salvează Configurația**: Salvează setările curente pentru utilizarea ulterioară

## Configurare

Aplicația folosește două fișiere de configurare:

- **themeconfig.json**: Configurarea temei interfeței grafice
- **schedule_config.json**: Configurarea opțiunilor de programare

## Licență

© 2024 Optimad

## Contacte și suport

Pentru întrebări și asistență, vă rugăm să contactați echipa de dezvoltare la adresa de email: support@optimad.com