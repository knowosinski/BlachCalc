# BlachCalc | Izo-Technika

Szybka instrukcja uruchomienia dla użytkownika: [INSTRUKCJA-URUCHOMIENIA.txt](./INSTRUKCJA-URUCHOMIENIA.txt).

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

1. Poproś autora o gotowy plik `BlachCalc-Setup.exe` i skopiuj go na komputer,
   na którym ma być zainstalowany program.
2. Kliknij plik dwukrotnie i przejdź przez kreator. Zostaw domyślne ustawienia
   lub wybierz, czy utworzyć ikonę na pulpicie.
3. Zakończ instalację. BlachCalc można uruchomić z menu Start, ikony na
   pulpicie lub bezpośrednio z ostatniej strony kreatora.
4. Przejdź scenariusz z sekcji [Lista kontrolna testów](#lista-kontrolna-testów).

Na komputerze docelowym nie trzeba instalować Pythona ani Inno Setup,
rozpakowywać archiwum ani uruchamiać plików `.bat` lub `.ps1`. Instalacja nie
wymaga uprawnień administratora.

## Instalacja

### Wymagania

- Windows 10 lub nowszy (64-bit),
- ok. 200 MB wolnego miejsca,
- brak wymaganych uprawnień administratora.

### Kroki

1. Skopiuj otrzymany od autora plik `BlachCalc-Setup.exe` na komputer.
2. Kliknij go dwukrotnie. W kreatorze zaakceptuj domyślny folder i wybierz,
   czy ma powstać skrót na pulpicie.
3. Kliknij **Zainstaluj**, a po zakończeniu **Zakończ**. Program znajdziesz
   w menu Start; kreator może też od razu go uruchomić.

Nie rozpakowuj instalatora. Na komputerze docelowym nie są potrzebne Python,
Inno Setup ani uprawnienia administratora.

Uruchomienie nowszego instalatora aktualizuje program. Jeśli BlachCalc jest
otwarty, instalator poprosi o jego zamknięcie. Baza danych, ustawienia i oferty
pozostają w osobnych folderach danych i nie są usuwane przy aktualizacji ani
odinstalowaniu.

### Windows SmartScreen i antywirus

Wydanie niepodpisane certyfikatem może nadal wywołać ostrzeżenie SmartScreen
lub fałszywy alarm antywirusa — nowy instalator nie gwarantuje, że każdy
produkt zabezpieczający zaakceptuje program. Nie wyłączaj ochrony i nie dodawaj
ogólnych wyjątków. Jeśli plik został zablokowany, nie uruchamiaj go; przekaż
informację o wykryciu autorowi aplikacji, aby próbka mogła zostać zgłoszona do
producenta antywirusa.

Najlepszym sposobem ograniczania ostrzeżeń w publicznych wydaniach jest
podpisanie aplikacji i instalatora zaufanym certyfikatem do podpisywania kodu
oraz zgłaszanie fałszywych alarmów do odpowiednich producentów. Podpis pomaga
zweryfikować wydawcę, ale sam w sobie nie gwarantuje braku ostrzeżeń.

## Odinstalowanie

Odinstaluj BlachCalc w **Ustawienia → Aplikacje → Zainstalowane aplikacje**
albo z folderu BlachCalc w menu Start. Usuwany jest program, skróty i wpis
deinstalatora. **Baza danych i wyeksportowane oferty zostają** (patrz
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
   Podczas edycji można zapisać zmiany do wybranej pozycji albo dodać osobną
   nową pozycję na podstawie zmodyfikowanych danych.
5. **Zatwierdź wycenę** zapisuje wycenę i otwiera podgląd oferty.

Wzór: materiał = cena/kg × masa, palenie = czas × stawka/godz., netto = suma,
VAT liczony od netto. Kwoty są zaokrąglane do groszy. Domyślna stawka materiału
4,70 zł/kg uwzględnia już założoną marżę firmową; program nie dolicza do niej
drugiego, osobnego narzutu.

### Podgląd i eksport

W podglądzie (renderowanym z tego samego PDF, który trafia do pliku) można:
zapisać ofertę do PDF, wyeksportować CSV, **Drukuj ofertę** bezpośrednio przez
domyślną aplikację PDF albo wrócić do edycji. **Generuj WZ** otwiera osobny
formularz wydania zewnętrznego.
Można rozpocząć nowy dokument bez zapisywania wyceny i bez wybierania
zamówienia z Historii; wystarczy uzupełnić dane odbiorcy, numer zamówienia i
własne pozycje. Z otwartego formularza wyceny dane klienta i pozycje są
kopiowane jako punkt startowy, a z zapisanej oferty — tak samo jak wcześniej —
można przejść do WZ bez zmieniania jej treści. Numer dokumentu i zamówienia w
WZ można edytować. Można poprawić ilość i opisy, dodać lub usunąć pozycje,
uzupełnić adres dostawy, osoby wydającą i odbierającą oraz opakowania. Przycisk
**Generuj WZ** jest dostępny w nawigacji niezależnie od zaznaczenia wyceny.
Roboczy WZ zapisuje się automatycznie i można do niego wrócić po ponownym
uruchomieniu aplikacji; przycisk **Nowe WZ** rozpoczyna kolejny dokument.
Podgląd WZ, tak jak podgląd oferty, jest wyświetlany wewnątrz aplikacji.
Przyciski **Drukuj WZ** i **Drukuj** wysyłają pełny dokument do domyślnej
drukarki przez systemową aplikację PDF; nie trzeba wcześniej zapisywać pliku
do wybranego folderu. Windows i domyślna aplikacja PDF muszą obsługiwać
polecenie drukowania. Roboczy PDF jest przechowywany tymczasowo i usuwany
przy kolejnym uruchomieniu, jeśli ma ponad 24 godziny.
Domyślnym miejscem zapisu jest `Dokumenty\OFERTY CENOWE BLACHCALC\WZ`. Oferty mają nazwę
`OF_<numer-zamówienia>_<klient>` (z kolejnym numerem, gdy plik już istnieje).
Dostępna jest też wewnętrzna karta kalkulacji z rozbiciem kosztów.

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
| Ctrl+S | zapisz wycenę; na podglądzie zapisz pełny PDF, w formularzu WZ zapisz szkic |
| Ctrl+N | nowe zamówienie |
| Ctrl+P | drukuj ofertę lub WZ / eksport PDF w historii |
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
- **Edycja drugiej strony oferty** — warunki, reklamacje, cennik palet oraz
  dowolnie dodawane rubryki z własnym nagłówkiem i treścią. Listę osób
  kontaktowych można rozbudowywać i porządkować przyciskami dodawania i
  usuwania. „Przywróć domyślne” cofa zmiany.
- **Kopie zapasowe** — ręczna kopia bazy i przywracanie. Kopie automatyczne
  powstają przy starcie i przed usunięciem wyceny (przechowywanych jest 30).

## Oferta PDF

Dwie lub więcej stron A4, zależnie od liczby pozycji i długości treści:

1. **Oferta handlowa** — dane zleceniodawcy, tabela pozycji (zdjęcie, ilość,
   masa sztuki, netto, brutto) oraz podsumowanie: razem netto, VAT, razem
   brutto. Opcjonalnie ważność, płatność i termin (puste domyślnie).
2. **Warunki** — dodatkowe warunki, odbiór i reklamacje, cennik palet,
   własne rubryki i osoby kontaktowe. Treść edytowalna w Ustawieniach.

Przy większej liczbie pozycji tabela kontynuuje się na kolejnych stronach,
powtarzając wiersz nagłówka. Każda strona zachowuje logo firmy, oznaczenie
kontynuacji, stopkę oraz numer strony z łączną liczbą stron.

Oferta używa polskich znaków w osadzonej czcionce (Arial/Segoe UI/Tahoma/DejaVu),
więc drukuje się poprawnie.

## Gdzie są dane

| Co | Gdzie |
| --- | --- |
| Baza, ustawienia, klienci, wyceny | `%LOCALAPPDATA%\BlachCalc\blachcalc.sqlite3` |
| Kopie zapasowe | `%LOCALAPPDATA%\BlachCalc\backups\` |
| Wyeksportowane oferty | `Dokumenty\OFERTY CENOWE BLACHCALC\` |
| Dokumenty WZ | `Dokumenty\OFERTY CENOWE BLACHCALC\WZ\` |
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
| Antywirus lub SmartScreen blokuje instalator | Nie wyłączaj ochrony ani nie dodawaj wyjątku. Zapisz nazwę wykrycia i wersję antywirusa, a następnie przekaż je autorowi do zgłoszenia fałszywego alarmu. |
| Instalator nie może zaktualizować programu | Zamknij BlachCalc i uruchom instalator ponownie. |
| Aplikacja nie startuje | Spróbuj uruchomić BlachCalc z menu Start i przekaż autorowi komunikat błędu. |
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

Te kroki wykonuje autor aplikacji na komputerze z kodem źródłowym, a nie osoba
instalująca program. Wymagane są Windows, Python 3.10+ dostępny jako `python`
w PowerShellu oraz Inno Setup 6 lub 7.

1. Zainstaluj Inno Setup 6 lub 7.
2. Otwórz PowerShell w głównym folderze projektu.
3. Uruchom:

```powershell
powershell -ExecutionPolicy Bypass -File .\Build-Windows.ps1
```

Skrypt najpierw uruchamia testy i sprawdza zależności, a następnie buduje
aplikację, instalator `release\BlachCalc-Setup.exe`, kopię instalatora
`BlachCalc-Setup.exe` w katalogu projektu oraz paczkę
`BlachCalc-Package.zip` z aktualnymi źródłami. Przekaż użytkownikowi sam
instalator — nie cały folder projektu ani folder `dist`. Na komputerze
docelowym uruchamia się wyłącznie `BlachCalc-Setup.exe`.

Jeżeli brakuje zależności, zainstaluj je jednorazowo poleceniem
`python -m pip install -r requirements-build.txt`.

Jeśli pojawi się komunikat, że nie znaleziono `ISCC.exe`, zainstaluj Inno Setup
6 lub 7 i ponownie uruchom powyższe polecenie. Nowy instalator zastępuje
poprzedni dopiero po poprawnym zbudowaniu.

Paczka projektu `BlachCalc-Package.zip` zawiera źródła i instalator
`BlachCalc-Setup.exe` bezpośrednio w głównym katalogu archiwum. Lokalne oferty
PDF i wygenerowane foldery budowania są pomijane; nie należy udostępniać ich
bez sprawdzenia, czy nie zawierają danych klientów.

Do szybkiego przebudowania i uruchomienia na komputerze deweloperskim:
`Rebuild-And-Run.bat` (lub `Rebuild-And-Run.ps1`).

### Struktura

| Plik | Zawartość |
| --- | --- |
| `blachcalc.py` | interfejs Tkinter |
| `calculator.py`, `quote_domain.py` | obliczenia i reguły kwot |
| `storage.py` | baza SQLite, ustawienia, kopie zapasowe |
| `exports.py` | eksport ofert i WZ do PDF oraz CSV |
| `offer_page.py` | edytowalna treść drugiej strony oferty |
| `app_paths.py` | ścieżki zasobów i eksportów |
| `test_*.py` | testy jednostkowe i okna |

### Licencja

Apache License 2.0 — patrz `LICENSE`.
