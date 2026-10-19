# BlachCalc | Izo-Technika

BlachCalc is Izo-Technika's Polish-language Windows desktop app for multi-part
sheet-metal cutting estimates, customer management, and branded offer exports.

The company logo, navy-and-red palette, and company details are preconfigured.
The document header uses **Izo-Technika Iłczyk Sp. Jawna**, ul. Wieniawskiego
18, 41-506 Chorzów; +48 786 300 750; k.nowosinski@izotechnika-cnc.pl;
www.izotechnika-cnc.pl; NIP 6272789387.
Business identity, contact details, logo, and default rates can be reviewed
and edited under **Ustawienia**.

## Instalacja na Windows

Paczka instalacyjna dla Windows jest dostępna w `release\BlachCalc-Installer.zip`.
Rozpakuj całe archiwum do wybranego folderu, a następnie dwukrotnie kliknij
`Instaluj BlachCalc.bat`. Instalator skopiuje aplikację do profilu użytkownika,
doda skrót do menu Start oraz utworzy na pulpicie ikonę BlachCalc. Po instalacji
wystarczy dwukrotnie kliknąć ikonę na pulpicie. Na komputerze nie trzeba
instalować Pythona.

Instalacja jest per-user i nie wymaga uprawnień administratora. Baza,
ustawienia i dane pozostają w `%LOCALAPPDATA%\BlachCalc`, niezależnie od
folderu instalacji. Eksporty domyślnie trafiają do
`Dokumenty\OFERTY CENOWE BLACHCALC`. Nie usuwaj folderu `App` z rozpakowanej
paczki przed uruchomieniem instalatora.
Do usunięcia programu uruchom `Odinstaluj BlachCalc.bat` z rozpakowanej
paczki. Odinstalowanie usuwa program i skróty, ale pozostawia lokalną bazę
danych oraz wyeksportowane oferty.

## Uruchamianie ze źródeł

Do pracy ze źródłami potrzebne są Windows 10 lub nowszy, Python 3.10+ oraz
Tkinter:

```powershell
python -m pip install -r requirements.txt
python blachcalc.py
```

## Budowanie instalatora

Na komputerze deweloperskim z Pythonem uruchom `Build-Windows.ps1`. Skrypt
zbuduje samodzielną aplikację, przygotuje ikonę Windows i zapisze paczkę
instalacyjną w `release\BlachCalc-Installer.zip`.

Authentication is temporarily disabled. If the database contains one account,
the app opens that account directly to preserve access to its existing
estimates. With no existing accounts, it creates a local workstation profile.
If several accounts exist, it creates or reuses a separate
`BlachCalc-local` profile and does not combine or display other users' private
estimates. Their accounts and data remain unchanged.

To restore the login and registration screen, set `LOGIN_ENABLED = True` in
`blachcalc.py`. While login is disabled, anyone with access to this computer can
open the active profile without entering a password. No data is sent to a
server.

## Navigate the workspace

Use the fixed left navigation to switch between **Nowa wycena**, **Historia
wycen**, **Kartoteka klientów**, and the saved estimate's **Podsumowanie
oferty**. The current order remains visible in the left panel while navigating:
customer and order number, added positions, quantity or batch scope, gross
total, edit/remove actions, and a new-order button. The **Zatwierdź wycenę**
action stays in a fixed bar beneath the quote form. The right side displays the
selected entry form, register, or branded offer preview.

## Estimate a job

1. Enter the customer and their order number.
2. Enter the part name, optional material and thickness, quantity, material
   price per kg, and the weight and burning time for one part.
3. Add each distinct part to the order. Adjust the material price, hourly
   burning rate, and VAT when needed; the defaults are **4.70 zł/kg**,
   **500 zł/hour**, and **23%**.
4. For each position, choose **Cała partia** to enter the combined weight and
   burning time of all pieces, or **Na sztukę** to enter one piece's weight and
   burning time plus the quantity. The form, labels, and add button update to
   match the selected calculation method. Both methods can be used within one
   estimate. For **Cała partia**, enter the final number of finished products
   separately: it is printed as the quantity but does not multiply the batch
   cost. For **Na sztukę**, quantity continues to multiply the per-piece cost.
5. Optionally attach a PNG, JPEG, GIF, BMP, WebP, or TIFF reference photo to
   each item. Photos (up to 10 MB each) are normalized and stored in the local SQLite database,
   shown in the editor and in the same offer-table row between the item
   description and quantity. The source filename is not shown in the app or
   included in the client PDF/CSV.
6. Select **Zatwierdź wycenę**. BlachCalc saves the estimate to the local
   database, assigns a unique `OF_<order-number>_<customer-name>` reference,
   stores a dated copy
   of the customer's contact details, and opens the branded offer preview.
7. From the preview, export the client-facing offer to PDF or the estimate
   details to CSV. Exports default to the `OFERTY CENOWE BLACHCALC` folder in
   the project directory and use the offer reference as the filename (a
   numeric suffix is added if an order/customer pair already exists).
   **Otwórz PDF do druku** saves and opens the offer in the
   system PDF viewer. Return to the form to edit the estimate.
8. In **Historia wycen**, double-click a saved estimate to edit it, or select
   **Podgląd oferty** to review its saved offer. Opening an estimate fills the
   header and loads its first position into the edit fields; all positions
   remain listed. Changes to an existing estimate update that record;
   **Kopiuj do nowej** creates a separate estimate. **Usuń** removes the
   estimate and its positions after confirmation. The calculation method is
   saved with each position. Drag the separator between the history list and
   actions to resize the panes. Press **Enter** in an editable field to move to
   the next field. Use the mouse wheel for vertical scrolling; hold **Alt**
   while scrolling to move horizontally in two-axis lists.
9. Right-click a position in the current order for **Edytuj**, **Usuń**, and
    **Podgląd** actions, or select it and press **Delete** to remove it.
10. On the quote page, **Ctrl+Z** undoes and **Ctrl+X** redoes recent field,
    photo, and order-position changes.

For each part, the app rounds unit material cost and unit burning cost to
grosze in **Na sztukę** mode. The unit net total is the sum of those costs; unit VAT is calculated
from the net total. The quantity is then applied to each unit amount, and order
totals are calculated by adding the rounded line amounts. The gross total is
net plus VAT. In **Cała partia** mode the combined material and burning costs
are rounded once for the complete batch; because of rounding, this total can
differ by a few grosze from calculating the same pieces individually.
**No margin or setup charge is applied.** These are production cost estimates,
not invoices.

## Exports

- **CSV** exports one row per order item with Izo-Technika seller details,
  customer, material, time, quantity, net, VAT, and gross amounts. It uses
  UTF-8 with BOM and semicolon separators for Polish spreadsheet compatibility.
  The photo column indicates whether a reference image is attached without
  including its source filename.
- **PDF** can produce either an Izo-Technika client-facing offer or a detailed
  internal cost sheet. The offer lists each position with its net, VAT, and
  gross value and shows its photo between the item description and quantity;
  the quantity always shows the number of finished products. The internal sheet
  includes combined material and burning breakdowns. PDF output uses the Izo-Technika logo, navy-and-red
  company palette, contact details, and a Polish-compatible system font when
  available.
- The on-screen offer preview is rendered from the same generated PDF as the
  export, so pagination, typography, images, and spacing match the saved file.
- Offer validity, payment terms, and delivery commitments are left blank by
  default, so documents do not imply unapproved commercial conditions.

## Customers and backups

The customer register stores company name, contact person, email, phone, NIP,
and address. Existing estimates keep a snapshot of customer details so that
later edits to the register do not silently change old documents.

Company and customer addresses use expandable structured fields for street,
building and optional unit numbers, postal code, city, and country. Polish
addresses require all fields except the unit number and are checked against the
`00-000` postal-code format. Existing free-form addresses are retained; common
Polish address formats are split into the corresponding fields automatically.

Accounts, customer records, settings, and estimates are kept in
`%LOCALAPPDATA%\BlachCalc\blachcalc.sqlite3`. Passwords are stored as salted
PBKDF2-HMAC-SHA256 hashes. Use **Ustawienia → Utwórz kopię zapasową bazy** to
save a consistent SQLite backup. The backup can contain all account and
customer data stored in that local database.

The first launch of the multi-item version migrates existing single-part
estimates without deleting the original records. Existing offer references are
updated to match the `OF_<order-number>_<customer-name>` export naming format.

## Tests

```powershell
python -m unittest
```
