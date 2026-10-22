# BlachCalc | Izo-Technika

BlachCalc to polskojęzyczna aplikacja desktopowa na Windows (Python, Tkinter,
ReportLab) do wycen cięcia laserem blach. Tworzy oferty handlowe w PDF z logo
Izo-Technika, prowadzi kartotekę klientów i historię wycen. Wszystkie dane są
przechowywane lokalnie na komputerze (SQLite) — aplikacja nie łączy się z
internetem.

- [Dla testera — szybki start](#dla-testera--szybki-start)
- [Instalacja](#instalacja)
- [Odinstalowanie](#odinstalowanie)
- [Jak korzystać](#jak-korzystać)
- [Ustawienia](#ustawienia)
- [Oferta PDF](#oferta-pdf)
- [Gdzie są dane](#gdzie-są-dane)
- [Lista kontrolna testów](#lista-kontrolna-testów)
- [Rozwiązywanie problemów](#rozwiązywanie-problemów)
- [Dla programistów](#dla-programistów)

## Dla testera — szybki start

1. Rozpakuj **cały** plik `BlachCalc-Installer.zip` do dowolnego folderu
   (prawy przycisk → *Wyodrębnij wszystkie*). Nie uruchamiaj plików z wnętrza
   archiwum bez rozpakowania.
2. Kliknij dwukrotnie `Install-BlachCalc.bat`.
3. Uruchom BlachCalc z ikony na pulpicie (instalator uruchamia go też sam).
4. Przejdź scenariusz z sekcji [Lista kontrolna testów](#lista-kontrolna-testów).

Python **nie jest potrzebny**. Instalacja nie wymaga uprawnień administratora.

## Instalacja

### Wymagania

- Windows 10 lub nowszy (64-bit),
- ok. 200 MB wolnego miejsca,
- brak wymaganych uprawnień administratora.

### Kroki

1. Rozpakuj pobrane archiwum `BlachCalc-Installer.zip`. W folderze muszą być:
   `App\`, `Install-BlachCalc.bat`, `Install-BlachCalc.ps1`,
   `Uninstall-BlachCalc.bat`, `Uninstall-BlachCalc.ps1`.
2. Uruchom `Install-BlachCalc.bat` (dwuklik).
3. Instalator:
   - kopiuje aplikację do `%LOCALAPPDATA%\Programs\BlachCalc`,
   - tworzy skrót **BlachCalc** na pulpicie i w menu Start,
   - uruchamia aplikację.
4. Folder z rozpakowanym archiwum można potem usunąć.

Ponowne uruchomienie instalatora **aktualizuje** program do nowej wersji.
Aktualizacja jest bezpieczna: nowa wersja najpierw jest kopiowana i sprawdzana,
a w razie błędu przywracana jest poprzednia. Dane (baza, ustawienia, oferty) nie
są ruszane.

### Ostrzeżenie Windows SmartScreen

Aplikacja nie jest podpisana certyfikatem, więc Windows może pokazać
niebieskie okno „System Windows chroni ten komputer”. Kliknij **Więcej
informacji → Uruchom mimo to**. Podobnie może zareagować przeglądarka lub
program antywirusowy na pobrany plik `.zip` / `.bat` — jeśli plik pochodzi od
Izo-Technika, odblokuj go (prawy przycisk na pliku `.zip` → *Właściwości* →
*Odblokuj*) **przed** rozpakowaniem.

## Odinstalowanie

Uruchom `Uninstall-BlachCalc.bat` z rozpakowanego archiwum. Usuwa program i
skróty. **Baza danych i wyeksportowane oferty zostają** (patrz
[Gdzie są dane](#gdzie-są-dane)); aby usunąć wszystko, skasuj ręcznie folder
`%LOCALAPPDATA%\BlachCalc` i folder `Dokumenty\OFERTY CENOWE BLACHCALC`.

## Jak korzystać

Po lewej jest stałe menu: **Nowa wycena**, **Historia wycen**, **Kartoteka
klientów** i **Podsumowanie oferty**. Bieżące zamówienie jest stale widoczne
w lewym panelu (klient, numer zamówienia, pozycje, suma brutto).

### Nowa wycena

1. Wybierz zleceniodawcę z listy (lub dodaj nowego w kartotece) i wpisz numer
   zamówienia.
2. Dla każdej pozycji uzupełnij kolejno (pola układają się w tej kolejności):
   1. **Nazwa elementu** oraz opcjonalnie **zdjęcie** z podglądem,
   2. **Materiał** (lista z Ustawień), **grubość**, **ilość**,
   3. **Masa**, **czas palenia**, **cena materiału**,
   4. **Stawka palenia** i **VAT** (pola tylko do odczytu — zmiana w Ustawieniach).
3. Wybierz sposób liczenia:
   - **Na sztukę** — wpisujesz masę i czas jednej sztuki, koszt jest mnożony
     przez ilość. Masa sztuki pojawia się w tabeli oferty.
   - **Cała partia** — wpisujesz łączną masę i czas wszystkich sztuk; ilość to
     liczba gotowych wyrobów i nie mnoży kosztu.
4. **Enter** przechodzi do następnego pola; Enter w ostatnim polu dodaje
   pozycję. Pozycje można edytować (prawy przycisk) i usuwać (**Delete**).
5. **Zatwierdź wycenę** zapisuje wycenę i otwiera podgląd oferty.

Wzór: materiał = cena/kg × masa, palenie = czas × stawka/godz., netto = suma,
VAT liczony od netto. Kwoty są zaokrąglane do groszy. Nie jest doliczana żadna
marża — to kalkulacja kosztów, nie faktura.

### Podgląd i eksport

W podglądzie (renderowanym z tego samego PDF, który trafia do pliku) można:
zapisać ofertę do PDF, wyeksportować CSV, **Otworzyć PDF do druku** albo
wrócić do edycji. Pliki trafiają do `Dokumenty\OFERTY CENOWE BLACHCALC` i mają
nazwę `OF_<numer-zamówienia>_<klient>` (z kolejnym numerem, gdy plik już
istnieje). Dostępna jest też wewnętrzna karta kalkulacji z rozbiciem kosztów.

### Historia i kartoteka

- **Historia wycen** — dwuklik otwiera wycenę do edycji, **Podgląd oferty**
  pokazuje zapisany dokument, **Kopiuj do nowej** tworzy osobną kopię,
  **Usuń** kasuje po potwierdzeniu.
- **Kartoteka klientów** — nazwa, osoba kontaktowa, e-mail, telefon, NIP i
  adres (ulica, numer, kod pocztowy `00-000`, miasto, kraj). Wycena zachowuje
  kopię danych klienta z dnia zapisu.

### Skróty klawiszowe (F1 — pomoc w aplikacji)

| Skrót | Działanie |
| --- | --- |
| Ctrl+S | zapisz wycenę |
| Ctrl+N | nowe zamówienie |
| Ctrl+P | PDF do druku / eksport PDF |
| Ctrl+Shift+D | kopiuj wycenę do nowej |
| Ctrl+Z / Ctrl+X | cofnij / ponów zmianę w formularzu |
| Ctrl+1…4 | Wycena, Historia, Klienci, Podsumowanie |
| F1 | pomoc |

Kółko myszy przewija obszar pod kursorem; z **Alt** przewija poziomo.

## Ustawienia

Przycisk **Ustawienia** w lewym menu:

- **Dane firmy** — nazwa, adres, telefon, e-mail, NIP, strona, hasło marki i
  logo (PNG/GIF) — trafiają do nagłówka PDF.
- **Stałe stawki** — cena materiału (domyślnie 4,70 zł/kg), stawka palenia
  (500 zł/godz.), VAT (23%). Tylko tutaj można je zmienić.
- **Materiały / gatunki blach** — lista dodawana raz, wybierana w formularzu.
- **Szerokość zdjęcia w ofercie PDF** — 25–56 mm (domyślnie 44).
- **Edycja drugiej strony oferty** — warunki, reklamacje, cennik palet i dane
  kontaktowe. „Przywróć domyślne” cofa zmiany.
- **Kopie zapasowe** — ręczna kopia bazy i przywracanie. Kopie automatyczne
  powstają przy starcie i przed usunięciem wyceny (przechowywanych jest 30).

## Oferta PDF

Dwie strony A4:

1. **Oferta handlowa** — dane zleceniodawcy, tabela pozycji (zdjęcie, ilość,
   masa sztuki, netto, brutto) oraz podsumowanie: razem netto, VAT, razem
   brutto. Opcjonalnie ważność, płatność i termin (puste domyślnie).
2. **Warunki** — dodatkowe warunki, odbiór i reklamacje, cennik palet,
   dane teleadresowe. Treść edytowalna w Ustawieniach.

Oferta używa polskich znaków w osadzonej czcionce (Arial/Segoe UI/Tahoma/DejaVu),
więc drukuje się poprawnie.

## Gdzie są dane

| Co | Gdzie |
| --- | --- |
| Baza, ustawienia, klienci, wyceny | `%LOCALAPPDATA%\BlachCalc\blachcalc.sqlite3` |
| Kopie zapasowe | `%LOCALAPPDATA%\BlachCalc\backups\` |
| Wyeksportowane oferty | `Dokumenty\OFERTY CENOWE BLACHCALC\` |
| Program | `%LOCALAPPDATA%\Programs\BlachCalc\` |

Aby przenieść dane na inny komputer: Ustawienia → Utwórz kopię zapasową, a na
drugim komputerze Ustawienia → Przywróć kopię. **Kopia zawiera wszystkie dane
(klientów, ceny) — traktuj ją jak poufną.**

Logowanie jest wyłączone (`LOGIN_ENABLED = False` w `blachcalc.py`): każdy
użytkownik Windows otwiera własny lokalny profil bez hasła.

## Lista kontrolna testów

Zaznacz, co działa, a co nie — wraz z opisem i zrzutem ekranu błędu.

- [ ] Instalacja i uruchomienie z ikony na pulpicie.
- [ ] Dodanie klienta w kartotece (z poprawnym adresem i kodem pocztowym).
- [ ] Dodanie materiałów w Ustawieniach i wybór z listy w wycenie.
- [ ] Wycena „Na sztukę” (2+ sztuki) i „Cała partia”, w jednym zamówieniu.
- [ ] Dodanie zdjęcia do pozycji; zmiana jego szerokości w Ustawieniach.
- [ ] Kolejność pól po Enter; Enter w ostatnim polu dodaje pozycję.
- [ ] Kółko myszy przewija wszędzie (formularz, lista, podgląd).
- [ ] Zmiana rozmiaru okna — nic się nie rozjeżdża.
- [ ] Zatwierdzenie wyceny, podgląd, zapis PDF; sprawdzenie kwot ręcznie.
- [ ] Polskie znaki (ł, ą, ę, ż…) w PDF — także po wydruku.
- [ ] Edycja drugiej strony oferty i jej odzwierciedlenie w PDF.
- [ ] Historia: edycja, kopia, usunięcie wyceny.
- [ ] Kopia zapasowa i jej przywrócenie.
- [ ] Zamknięcie i ponowne uruchomienie — dane są zachowane.
- [ ] Odinstalowanie.

## Rozwiązywanie problemów

| Problem | Rozwiązanie |
| --- | --- |
| „Nie znaleziono pliku App\BlachCalc.exe” | Archiwum nie zostało w całości rozpakowane. Rozpakuj je ponownie. |
| SmartScreen blokuje uruchomienie | Więcej informacji → Uruchom mimo to. |
| Antywirus usuwa plik | Dodaj folder instalacji do wyjątków lub odblokuj `.zip` przed rozpakowaniem. |
| Okno instalatora znika zbyt szybko | Uruchom `powershell -ExecutionPolicy Bypass -File Install-BlachCalc.ps1` w wierszu poleceń i prześlij komunikat. |
| Aplikacja nie startuje | Uruchom `BlachCalc.exe` z `%LOCALAPPDATA%\Programs\BlachCalc` i prześlij komunikat błędu. |
| Brak polskich liter w PDF | Aplikacja wymaga jednej z czcionek: Arial, Segoe UI, Tahoma, DejaVu. Na Windows są standardowo dostępne. |

Zgłaszając błąd podaj: wersję Windows, kroki do odtworzenia, komunikat błędu i
zrzut ekranu. Nie wysyłaj bazy danych bez zgody właściciela — zawiera dane klientów.

## Dla programistów

### Uruchamianie ze źródeł

Wymagane: Windows 10+, Python 3.10+ (z Tkinterem).

```powershell
python -m pip install -r requirements.txt
python blachcalc.py
```

### Testy

```powershell
python -m unittest discover -p "test_*.py"
```

Testy okna (`test_app_ui.py`) wymagają środowiska graficznego; bez niego są
pomijane.

### Budowanie paczki instalacyjnej

```powershell
powershell -ExecutionPolicy Bypass -File .\Build-Windows.ps1
```

Skrypt instaluje zależności z `requirements-build.txt`, tworzy ikonę, buduje
aplikację PyInstallerem (`dist\BlachCalc`) i składa paczkę
`release\BlachCalc-Installer.zip` (aplikacja + instalator + deinstalator +
README). Nowa paczka zastępuje poprzednią dopiero po poprawnym zbudowaniu.
Budowanie trwa kilka minut.

Do szybkiego przebudowania i uruchomienia na komputerze deweloperskim:
`Rebuild-And-Run.bat` (lub `Rebuild-And-Run.ps1`).

### Struktura

| Plik | Zawartość |
| --- | --- |
| `blachcalc.py` | interfejs Tkinter |
| `calculator.py`, `quote_domain.py` | obliczenia i reguły kwot |
| `storage.py` | baza SQLite, ustawienia, kopie zapasowe |
| `exports.py` | eksport PDF i CSV |
| `offer_page.py` | edytowalna treść drugiej strony oferty |
| `app_paths.py` | ścieżki zasobów i eksportów |
| `test_*.py` | testy jednostkowe i okna |

### Licencja

Apache License 2.0 — patrz `LICENSE`.
