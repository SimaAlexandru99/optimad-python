# Ghidul utilizatorului Optimad

## Cuprins

1. [Introducere](#introducere)
2. [Instalare și configurare](#instalare-și-configurare)
3. [Interfața utilizator](#interfața-utilizator)
4. [Configurarea capturilor de ecran](#configurarea-capturilor-de-ecran)
5. [Opțiuni de planificare](#opțiuni-de-planificare)
6. [Procesul de capturare](#procesul-de-capturare)
7. [Depanare](#depanare)
8. [Întrebări frecvente](#întrebări-frecvente)

## Introducere

Optimad este o aplicație specializată pentru capturarea automată a ecranului, proiectată pentru a facilita documentarea activității online. Aplicația permite utilizatorilor să programeze capturi de ecran la intervale regulate, să modifice temporar data sistemului și să focalizeze pe aplicații specifice cum ar fi Zoom, Microsoft Teams sau Google Chrome.

### Scopul aplicației

Aplicația a fost concepută pentru a ajuta utilizatorii să:
- Documenteze automat activitatea de pe ecran
- Simuleze activitate desfășurată în mai multe zile consecutive
- Automatizeze procesul de capturare pentru diferite platforme

## Instalare și configurare

### Cerințe sistem

- **Sistem de operare**: Windows 10 sau mai recent
- **Python**: Versiunea 3.8 sau mai nouă
- **Drepturi**: Administrator (pentru modificarea datei sistemului)
- **Spațiu pe disc**: Minim 500 MB disponibil

### Procedura de instalare

#### Metoda 1: Folosind script-ul de instalare automată

1. Deschideți Command Prompt sau PowerShell
2. Navigați la directorul aplicației
3. Executați script-ul de configurare:
   ```
   python setup.py
   ```
4. După finalizare, activați mediul virtual:
   ```
   .venv\Scripts\activate
   ```

#### Metoda 2: Instalare manuală

1. Creați un mediu virtual:
   ```
   python -m venv .venv
   ```
2. Activați mediul virtual:
   ```
   .venv\Scripts\activate
   ```
3. Instalați dependențele:
   ```
   pip install -r requirements.txt
   ```

### Prima pornire

Pentru funcționalitate completă, aplicația trebuie rulată cu drepturi de administrator. Utilizați unul din script-urile furnizate:

- `run_admin.bat` (pentru Windows)
- `run_admin.ps1` (pentru PowerShell)

Alternativ, puteți deschide Command Prompt cu drepturi de administrator și executa:
```
python main.py
```

## Interfața utilizator

Interfața aplicației Optimad este organizată în mai multe secțiuni pentru ușurință în utilizare:

### Tab-ul "Setari"

Acest tab conține majoritatea controalelor pentru configurarea și operarea aplicației:

#### Secțiunea "Configurari Capturi"

- **Ore de curs**: Numărul de ore care vor fi simulate
- **Numar de capturi de ecran**: Câte capturi vor fi realizate

#### Secțiunea "Selecteaza aplicația"

Alegeți aplicația care va fi focalizată înainte de realizarea capturilor:
- Desktop (implicit)
- Zoom
- Microsoft Teams
- Google Chrome

#### Secțiunea "Optiuni de pornire"

Alege când să înceapă procesul de capturare:
- **Incepe acum**: Pornire imediată
- **Incepe la ora specificata**: Setează o oră precisă pentru pornire (format HH:MM)
- **Ruleaza zilnic la ora specificata**: Programează rularea zilnică la ora stabilită

#### Secțiunea "Progres"

Afișează informații despre progresul capturilor:
- Timp rămas până la următoarea captură
- Numărul de capturi realizate
- Data și ora următoarei rulări programate (pentru rulare zilnică)

### Tab-ul "Despre"

Conține informații generale despre aplicație, versiune și funcționalități.

## Configurarea capturilor de ecran

### Parametrii de configurare

#### Ore de curs

Introduceți un număr între 1 și 24 pentru a defini durata perioadei simulate. Pentru fiecare oră specificată, aplicația va simula o zi diferită prin modificarea datei sistemului.

#### Număr de capturi

Specificați câte capturi doriți să realizați în timpul simulării. Valoarea trebuie să fie între 1 și 60. Aplicația va distribui aceste capturi pe perioada definită de orele de curs.

> **Notă importantă**: Intervalul minim între capturi este de 1 minut. Dacă setările dvs. ar rezulta într-un interval mai mic, aplicația va afișa o eroare.

### Formatul și calitatea capturilor

Implicit, capturile sunt salvate în format PNG pentru calitate optimă. Locația capturilor este organizată în directoare după data simulată:
```
[Director aplicație]/[YYYY-MM-DD]/[HH-MM-SS].png
```

## Opțiuni de planificare

### Pornire imediată

Opțiunea "Începe acum" va porni procesul de capturare imediat după apăsarea butonului "Pornește Procesul".

### Pornire programată

Opțiunea "Începe la ora specificată" permite programarea unui moment specific pentru începerea capturilor. Trebuie să specificați ora în formatul HH:MM (24 de ore).

### Rulare zilnică

Opțiunea "Rulează zilnic la ora specificată" configurează aplicația să execute automat procesul de capturare în fiecare zi la ora stabilită. Această setare este salvată și rămâne activă chiar și după închiderea și redeschiderea aplicației.

### Salvarea configurației

Pentru a păstra setările pentru utilizări viitoare, apăsați butonul "Salvează Configurația". Aceasta va actualiza fișierul `schedule_config.json` cu valorile curente.

## Procesul de capturare

### Secvența de capturare

1. **Inițiere**: Aplicația verifică validitatea setărilor introduse
2. **Pregătire**: Se face un countdown inițial (15 secunde) înainte de prima captură
3. **Capturare și simulare**:
   - Se focalizează pe aplicația selectată
   - Se realizează captura de ecran
   - Se modifică data sistemului pentru a simula ziua următoare
   - Se repetă procesul pentru numărul specificat de capturi
4. **Finalizare**: La sfârșitul procesului, data sistemului este restaurată la valoarea inițială

### Monitorizarea progresului

În timpul procesului de capturare, interfața afișează:
- Timpul rămas până la următoarea captură
- Numărul de capturi realizate și totalul planificat
- O bară de progres pentru vizualizare rapidă

### Întreruperea procesului

Procesul de capturare poate fi oprit în orice moment apăsând butonul "Oprește Procesul". Aplicația se va asigura că data sistemului este restaurată corect înainte de încheierea procesului.

## Depanare

### Erori comune și soluții

#### Eroare: "Nu s-a putut seta data sistemului"

**Cauză posibilă**: Aplicația nu are drepturi suficiente pentru a modifica data sistemului.
**Soluție**: 
1. Asigurați-vă că rulați aplicația cu drepturi de administrator
2. Verificați că nu există alte programe care blochează modificarea datei sistemului

#### Eroare: "Nu s-a putut realiza captura de ecran"

**Cauză posibilă**: Aplicația nu poate accesa ecranul sau nu are permisiuni suficiente.
**Soluție**:
1. Verificați că aplicația țintă (Zoom, Teams etc.) este deschisă și vizibilă
2. Asigurați-vă că nu există ferestre de dialog sau notificări care blochează aplicația

#### Eroare: "Format de timp invalid"

**Cauză posibilă**: Formatul orei introduse pentru programare este incorect.
**Soluție**: Asigurați-vă că respectați formatul HH:MM (exemplu: 14:30)

### Jurnalul de erori

Aplicația păstrează un jurnal detaliat al operațiunilor în directorul `logs`. Fișierul `jurnal_erori.txt` conține toate mesajele de sistem și erorile întâmpinate. Consultați acest fișier pentru informații detaliate în cazul problemelor.

## Întrebări frecvente

**Î: Este sigur să modific data sistemului?**

R: Modificarea datei sistemului ar putea afecta temporar alte aplicații care depind de data și ora corectă. Optimad restaurează data originală după finalizarea procesului, dar este recomandat să nu rulați alte aplicații importante în paralel.

**Î: Pot captura ecranul unei aplicații chiar dacă nu e vizibilă?**

R: Nu. Aplicația țintă trebuie să fie vizibilă pe ecran pentru a fi capturată corect. Optimad încearcă să aducă aplicația în prim-plan, dar există limitări în funcție de modul în care aplicația răspunde.

**Î: Pot modifica locația unde sunt salvate capturile?**

R: În versiunea actuală, locația este predefinită în directorul aplicației. O versiune viitoare va permite personalizarea acestei locații.

**Î: Ce se întâmplă dacă computerul intră în repaus în timpul unui proces programat?**

R: Dacă computerul intră în repaus, procesul de capturare va fi întrerupt. Este recomandat să dezactivați repausul automat în timpul utilizării aplicației sau să folosiți setări de alimentare care să mențină computerul activ.