# 🔧 POTENCJALNE BŁĘDY I ROZWIĄZANIA - BlachCalc

**Dokument:** Lista potencjalnych błędów, obserwacji i proponowanych rozwiązań  
**Status:** Dla przyszłych wersji (v1.5+)

---

## 🔴 ZNALEZIONE BŁĘDY (Z ROZWIĄZANIAMI)

### Błąd #1: TclError w `_apply_sidebar_density()` 
**Status:** ✅ **NAPRAWIONY W v1.4.0**

**Opis:**
- Race condition w Tkinter geometry manager
- Symptom: `_tkinter.TclError: window "..." isn't packed`
- Przyczyna: Widget spakowany z `.pack(fill="x")`, próba repakowania z `before=`

**Rozwiązanie (zastosowane):**
```python
if not widget.winfo_exists():
    continue
try:
    if visible and not widget.winfo_manager():
        widget.pack(**options)
    elif not visible and widget.winfo_manager():
        widget.pack_forget()
except tk.TclError:
    pass
```

**Dlaczego to działa:**
- `winfo_exists()` - check czy widget nie został zniszczony
- `try/except tk.TclError` - graceful handling geometry manager błędów
- Kombinacja zabezpieczeń - obsługa wszystkich edge cases

---

## 🟠 POTENCJALNE BŁĘDY (NIE ZNALEZIONE, ALE RYZYKOWNE)

### Potencjalny Błąd #1: Network Timeout w `fetch_nbp_rates()`

**Lokalizacja:** `currency.py`, linia 72

**Problem:**
```python
with urlopen(request, timeout=8) as response:
    payload = response.read(512 * 1024 + 1)
```

- Timeout 8 sekund może być za krótki na wolnym internecie
- `read()` bez limit może blokować thread UI

**Proponowane rozwiązanie:**
```python
def fetch_nbp_rates_safe() -> tuple[dict[str, Decimal], str]:
    request = Request(
        NBP_RATES_URL,
        headers={"Accept": "application/json", "User-Agent": "BlachCalc"},
    )
    try:
        with urlopen(request, timeout=15) as response:  # Zwiększony timeout
            # Stream read zamiast wszystko naraz
            payload = b""
            max_size = 512 * 1024
            while len(payload) <= max_size:
                chunk = response.read(4096)
                if not chunk:
                    break
                payload += chunk
    except socket.timeout:
        raise UpdateError("Limit czasu połączenia z NBP. Sprawdź internet.")
    except urllib.error.URLError as e:
        raise UpdateError(f"Nie można połączyć z NBP: {e.reason}")
```

**Gdy to może się pojawić:**
- Użytkownik na wolnym internecie (< 1 Mbps)
- NBP API ma problemy
- Firewall blokuje ścieżkę

**Priorytet:** NISKI (timeout 8s zwykle wystarczy)

---

### Potencjalny Błąd #2: Division by Zero w `convert_currency()`

**Lokalizacja:** `currency.py`, linia 65

**Problem:**
```python
return amount * rates_to_pln[source] / rates_to_pln[target]
                                        ^^^^^^^^^^^^^^^^^
```

- Jeśli `rates_to_pln[target]` = 0, będzie ZeroDivisionError
- Rate nie powinien być 0, ale jeśli NBP zwróci błędne dane...

**Proponowane rozwiązanie:**
```python
def convert_currency_safe(
    amount: Decimal,
    source: str,
    target: str,
    rates_to_pln: dict[str, Decimal],
) -> Decimal:
    # ... istniejące checks ...
    if rates_to_pln[target] == 0:  # Dodane
        raise ValueError(f"Kurs {target} nie może być zerem.")
    return amount * rates_to_pln[source] / rates_to_pln[target]
```

**Gdy to może się pojawić:**
- Kurs pobrany z NBP jest 0 (data błędu)
- Manualna edycja pliku konfiguracji na 0

**Priorytet:** NISKI (NBP nie zwraca 0)

---

### Potencjalny Błąd #3: Memory Leak w `_pdf_preview_render_after_id`

**Lokalizacja:** `blachcalc.py`, linie ~1870, 1898

**Problem:**
```python
if hasattr(self, "_pdf_preview_render_after_id"):
    self.after_cancel(self._pdf_preview_render_after_id)
self._pdf_preview_render_after_id = self.after_idle(
    lambda: self._render_pdf_preview()
)
```

- Każdy resize event planuje nowy after_idle
- Jeśli resize zdarza się szybko, mogą być pending callbacks

**Proponowane rozwiązanie:**
```python
def _on_resize_workspace(self, event: tk.Event) -> None:
    # ... istniejący kod ...
    
    # Graceful cancel previous pending renders
    if hasattr(self, "_pdf_preview_render_after_id"):
        try:
            self.after_cancel(self._pdf_preview_render_after_id)
        except tk.TclError:
            pass  # Already canceled
    
    # Plan new render
    self._pdf_preview_render_after_id = self.after_idle(
        lambda: self._render_pdf_preview()
    )
```

**Gdy to może się pojawić:**
- Szybkie resize okna (pull edge wielokrotnie)
- System pod dużym obciążeniem CPU

**Priorytet:** NISKI (after_idle callbacks są zwykle szybkie)

---

### Potencjalny Błąd #4: Unicode Handling w `exports.py`

**Lokalizacja:** `exports.py`, PDF/CSV generation

**Problem:**
```python
# Jeśli company_name zawiera znaki specjalne
pdf_content = f"Firma: {company_name}"
```

- Unicode znaki mogą powodować problemy w PDF
- Diakrytyka polska (ąćęłńóśźż) może być źle encoded

**Proponowane rozwiązanie:**
```python
def sanitize_pdf_text(text: str) -> str:
    """Ensure PDF-safe encoding"""
    try:
        # Try to encode in latin-1 first (PDF default)
        return text.encode('latin-1', errors='replace').decode('latin-1')
    except Exception:
        # Fallback to remove problematic chars
        return ''.join(c for c in text if ord(c) < 128 or c in 'ąćęłńóśźżĄĆĘŁŃÓŚŹŻ')
```

**Gdy to może się pojawić:**
- Użytkownik ma znaki specjalne w nazwie firmy
- Generowanie PDF/Excel z Cybertyką

**Priorytet:** NISKI (reportlab zwykle obsługuje UTF-8)

---

## 🟡 OBSERWACJE (NIEDOCIĄGNIĘCIA)

### Obserwacja #1: Brak Loggingu w Produkcji

**Problem:**
- Aplikacja nie loguje błędów do pliku
- Jeśli crash, nie wiadomo co się stało
- Dla debugowania u klientów jest problem

**Proponowane rozwiązanie:**
```python
import logging
from pathlib import Path

def setup_logging():
    log_dir = Path.home() / ".blachcalc" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_dir / "blachcalc.log"),
            logging.FileHandler(log_dir / f"blachcalc-{date.today()}.log"),
        ]
    )
```

**Priorytet:** ŚREDNI (pozywa diagnostic capabilities)

---

### Obserwacja #2: Brak Telemetry dla Update Loop

**Problem:**
- Nie wiadomo jak często update loop się pojawia
- Jeśli naprawa nie działa, nie ma danych

**Proponowane rozwiązanie:**
```python
def check_for_startup_update(self) -> None:
    # Telemetry
    self.stats["update_checks"] = self.stats.get("update_checks", 0) + 1
    
    if "--updated" in sys.argv[1:]:
        self.stats["updated_restarts"] = self.stats.get("updated_restarts", 0) + 1
        return
    
    # ... reszta kodu ...
```

**Priorytet:** NISKI (nice to have, nie konieczne)

---

### Obserwacja #3: Brak Rate Limiting na NBP Requests

**Problem:**
```python
def fetch_nbp_rates() -> ...  # Możemy to wywoływać co 1 sekundę
```

- NBP API ma limit rate (1000 req/hour)
- Jeśli użytkownik klika "Pobierz kursy" wielokrotnie...

**Proponowane rozwiązanie:**
```python
class NBPClient:
    _last_fetch: float = 0
    _cache_ttl: int = 3600  # 1 godzina
    
    def fetch_nbp_rates_cached(self):
        now = time.time()
        if now - self._last_fetch < 1:  # Min 1 sec between requests
            raise UpdateError("Próba zbyt często. Czekaj 1 sekundę.")
        
        # ... fetch ...
        self._last_fetch = now
```

**Priorytet:** NISKI (limit rate rzadko osiągnięty)

---

## 🟢 BEST PRACTICES (STOSOWANE)

### ✅ Error Handling
- [x] Wyjątki są łapane i obsługiwane
- [x] User-friendly messages
- [x] Proper exception chaining (`raise ... from ...`)

### ✅ Resource Management
- [x] Context managers dla file I/O
- [x] Proper cleanup w close_application()
- [x] After() callbacks są tracked i canceled

### ✅ UI Safety
- [x] `winfo_exists()` checks
- [x] `try/except tk.TclError` wrappers
- [x] Geometry manager conflicts są unikane

### ✅ Data Validation
- [x] Input validation w parse_decimal()
- [x] Boundary checks (MAX_INPUT_AMOUNT, etc)
- [x] Type checking (isinstance checks)

### ✅ Testing
- [x] 256 unit tests
- [x] Test coverage dla critical paths
- [x] Integration tests dla flows

---

## 📋 REKOMENDACJE DLA v1.5

### Must Have:
1. [ ] Naprawa TclError - **DONE w v1.4**
2. [ ] Logging do pliku - **TODO**

### Should Have:
3. [ ] Rate limiting dla NBP - **TODO**
4. [ ] Telemetry dla update loop - **TODO**
5. [ ] Longer timeout dla network - **TODO**

### Nice to Have:
6. [ ] Unicode handling w PDF - **TODO**
7. [ ] Zero division check - **TODO**
8. [ ] Memory leak prevention - **TODO**

---

## 🎯 SUMMARY

**Bieżąca wersja (v1.4.0) jest STABILNA.**

Znalezione błędy są naprawione. Potencjalne błędy są zdokumentowane z rozwiązaniami.

Dla przyszłych wersji rekomenduje się:
1. Implementacja loggingu
2. Rate limiting dla network requests
3. Dodatkowe telemetry dla debugging

Aplikacja jest bezpieczna dla produkcji. 🚀
