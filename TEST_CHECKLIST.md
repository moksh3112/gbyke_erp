# G-Byke ERP — Full Manual Test Checklist

Mark each item **Y** (works) or **N** (broken). Work top-to-bottom — later sections depend on data created earlier.
Legend: ⭐ = built/fixed recently, pay extra attention.

---

## 0. Server & Startup

| # | Test | Y/N |
|---|------|-----|
| 0.1 | Backend server starts with no errors in console | |
| 0.2 | Console prints "✓ Migrations applied" and "✓ All tables ready" | |
| 0.3 | `scooter_models` has a row with `model_code = 'GEN'` | |
| 0.4 | ⭐ `damage_records` table has `dealer_id` and `part_name_free` columns | |
| 0.5 | Desktop app launches and shows login screen | |
| 0.6 | Stopping the server then using the app shows a clean "Cannot connect" error (no crash) | |

---

## 1. Authentication & Roles

| # | Test | Y/N |
|---|------|-----|
| 1.1 | Login with correct superadmin credentials succeeds | |
| 1.2 | Login with wrong password shows an error, does not log in | |
| 1.3 | Login with blank fields is blocked | |
| 1.4 | Superadmin lands on Admin Dashboard | |
| 1.5 | Logout returns to login screen | |
| 1.6 | Login as **manager** — can add/edit dealers, models, BOM | |
| 1.7 | Login as **manager** — cannot delete/deactivate (superadmin-only actions hidden) | |
| 1.8 | Login as **staff/operator** — read-only where expected, no add/edit buttons | |
| 1.9 | Session token persists across screen navigation (no re-login) | |

---

## 2. Admin Dashboard

| # | Test | Y/N |
|---|------|-----|
| 2.1 | Cards load: Total Inventory Items, Low Stock Alerts, Total Consumed, Total Defective | |
| 2.2 | ⭐ NO "Inventory Value" card present | |
| 2.3 | Welcome message shows logged-in username | |
| 2.4 | Numbers match actual data (cross-check with Inventory screen) | |

---

## 3. Master Data

### 3a. Scooter Models
| # | Test | Y/N |
|---|------|-----|
| 3.1 | Model list loads | |
| 3.2 | ⭐ "General Parts" (GEN) model does NOT appear in this list | |
| 3.3 | Add a new model — appears in list | |
| 3.4 | Duplicate model name is rejected | |
| 3.5 | Duplicate model code is rejected | |
| 3.6 | Edit model name — saves | |
| 3.7 | Deactivate model — disappears from active list | |

### 3b. Colors
| # | Test | Y/N |
|---|------|-----|
| 3.8 | Colors load | |
| 3.9 | Add color — appears | |
| 3.10 | Duplicate color rejected | |
| 3.11 | Delete color — removed | |

### 3c. Batteries
| # | Test | Y/N |
|---|------|-----|
| 3.12 | Batteries load | |
| 3.13 | Add battery (type + power spec) — appears | |
| 3.14 | Duplicate battery config rejected | |
| 3.15 | Delete battery — removed | |

### 3d. Locations
| # | Test | Y/N |
|---|------|-----|
| 3.16 | Locations load (factory/warehouse/godown) | |
| 3.17 | Add location — appears | |
| 3.18 | Invalid location type rejected | |
| 3.19 | Edit location — saves | |
| 3.20 | Deactivate location — disappears from active list | |

### 3e. ⭐ General Parts
| # | Test | Y/N |
|---|------|-----|
| 3.21 | "⚙️ General Parts" tab is visible (5th tab) | |
| 3.22 | Add "12V Battery" — SKU auto-generates as `GEN-12VBATTERY` | |
| 3.23 | Added part appears in the table with correct SKU | |
| 3.24 | Add "Charger" and "Tyre" — both appear | |
| 3.25 | ⭐ Adding a DUPLICATE part name is blocked with an error | |
| 3.26 | Delete a general part — disappears | |

---

## 4. BOM (Bill of Materials)

| # | Test | Y/N |
|---|------|-----|
| 4.1 | Select a model — its BOM list loads | |
| 4.2 | Add a BOM part (name + qty) — auto-generates a model-specific SKU (e.g. `BIRDY210-ALARM`) | |
| 4.3 | SKU is stored and shown in BOM list | |
| 4.4 | ⭐ Adding a duplicate part name to the same model is blocked | |
| 4.5 | Add same part name (e.g. "Alarm") to TWO different models → each gets its own distinct SKU | |
| 4.6 | Edit a BOM item — saves | |
| 4.7 | Delete a BOM item — removed | |

---

## 5. Inventory

### 5a. Table layout
| # | Test | Y/N |
|---|------|-----|
| 5.1 | ⭐ Column order is Model first, then Part Name | |
| 5.2 | All text is visible (dark, not white-on-white) | |
| 5.3 | Search by part name works | |
| 5.4 | Search by model name works | |
| 5.5 | "Spare parts only" filter button works | |

### 5b. Add Stock — model-specific
| # | Test | Y/N |
|---|------|-----|
| 5.6 | Open "Add Stock Entry", Entry Type = Purchase | |
| 5.7 | Select a model → Part Name dropdown loads ONLY that model's BOM parts | |
| 5.8 | Cannot type free text into part name (dropdown only) | |
| 5.9 | SKU auto-fills from BOM, shows green "✓ from BOM" | |
| 5.10 | Pick colour + location + qty → Save → item appears in table | |
| 5.11 | ⭐ Two models with the same part name save under their correct distinct SKUs | |

### 5c. Add Stock — General / No Model ⭐
| # | Test | Y/N |
|---|------|-----|
| 5.12 | Select "⚙ General / No Specific Model" → Part dropdown loads from General Parts list | |
| 5.13 | Pick "12V Battery [GEN-12VBATTERY]" → SKU auto-fills | |
| 5.14 | Enter qty → Save → succeeds (NO "Model name required" error) | |
| 5.15 | Battery appears in inventory table | |

### 5d. Log Defective stock
| # | Test | Y/N |
|---|------|-----|
| 5.16 | "Log Defective" opens form | |
| 5.17 | ⭐ Select "General / No Specific Model" → pick Battery → Save succeeds (no model error) | |
| 5.18 | Defective qty increments, remaining qty decrements | |
| 5.19 | Admin dashboard "Total Defective" reflects the change | |

### 5e. Thresholds
| # | Test | Y/N |
|---|------|-----|
| 5.20 | Item below low-stock threshold shows a low-stock indicator | |
| 5.21 | Low Stock Alerts count on dashboard updates | |

---

## 6. Manufacturing

| # | Test | Y/N |
|---|------|-----|
| 6.1 | Create assembly job (model + qty + date) — appears in list | |
| 6.2 | Start job — status changes | |
| 6.3 | Complete job — creates one scooter unit per qty | |
| 6.4 | Created units appear in PDI/Warehouse with status "assembled" | |
| 6.5 | Cancel job — status = cancelled | |
| 6.6 | ⭐ Delete a cancelled job — succeeds with NO foreign-key error | |
| 6.7 | BOM for selected model shows correct model-specific SKUs | |

---

## 7. PDI (Pre-Delivery Inspection)

| # | Test | Y/N |
|---|------|-----|
| 7.1 | PDI list loads assembled units | |
| 7.2 | Start PDI — status → pdi_in_progress | |
| 7.3 | Complete PDI — status → pdi_done, PDI number assigned | |
| 7.4 | Search by serial number works | |
| 7.5 | Search by PDI number works | |
| 7.6 | A non-assembled unit cannot be PDI'd again | |

---

## 8. Warehouses / Godowns

| # | Test | Y/N |
|---|------|-----|
| 8.1 | "All Locations" overview loads with unit counts | |
| 8.2 | Stat cards (Locations, Units, PDI Done, Delivered) populate | |
| 8.3 | "View →" opens a per-location drill-down tab | |
| 8.4 | ⭐ Status filter dropdown actually filters the units list | |
| 8.5 | Free-text search filters the units table | |
| 8.6 | Refresh button reloads | |
| 8.7 | Transfer a unit to another location → success message | |
| 8.8 | After transfer, unit appears at the new location and not the old | |
| 8.9 | Close drill-down tab works (overview tab can't be closed) | |

---

## 9. Dealers

### 9a. List & CRUD
| # | Test | Y/N |
|---|------|-----|
| 9.1 | Dealer list loads (name, code, city, state, units, status) | |
| 9.2 | Search by name/code/city/state works | |
| 9.3 | Add dealer — auto-generates dealer code, appears | |
| 9.4 | Edit dealer — saves | |
| 9.5 | Deactivate (superadmin) — marked inactive | |
| 9.6 | Reactivate — marked active | |
| 9.7 | Delete permanently (superadmin) — removed (blocked if units assigned) | |

### 9b. Actions menu ⭐
| # | Test | Y/N |
|---|------|-----|
| 9.8 | "⚡ Actions ▾" opens the dropdown | |
| 9.9 | "🔍 View Units" opens a tab of all scooters at that dealer | |
| 9.10 | ⭐ "📦 View Spare Parts" opens a dialog of all parts dispatched to that dealer | |
| 9.11 | ⭐ "⚠️ Log Spare Part Damage" opens the spare-part damage dialog | |

### 9c. Scooter damage ⭐
| # | Test | Y/N |
|---|------|-----|
| 9.12 | In "View Units", click "⚠ Damage" on a unit | |
| 9.13 | ⭐ Part dropdown is populated from that scooter model's BOM + General Parts | |
| 9.14 | ⭐ "Other (describe below)" reveals a free-text field | |
| 9.15 | Stage options: "During Transportation to Dealer" / "After Sale" | |
| 9.16 | Save → success; record shows in Damage Log → After Sale | |

### 9d. Spare part damage ⭐
| # | Test | Y/N |
|---|------|-----|
| 9.17 | ⭐ Spare-part damage dialog's part dropdown lists parts previously sent to that dealer | |
| 9.18 | ⭐ "Other" option allows free text | |
| 9.19 | Damage notes are required | |
| 9.20 | Save → success | |
| 9.21 | ⭐ Record appears in Damage Log → After Sale with "🔧 Spare Part" label | |

---

## 10. Shipments (Dispatch)

### 10a. Create dispatch
| # | Test | Y/N |
|---|------|-----|
| 10.1 | "＋ New Dispatch" opens dialog (manager/superadmin only) | |
| 10.2 | Confirm with no dealer selected → blocked | |
| 10.3 | Add Scooter → enter PDI number → Verify → shows model/colour/serial in green | |
| 10.4 | Verify invalid PDI → red error | |
| 10.5 | Verify already-dispatched PDI → blocked | |
| 10.6 | Verify non-pdi_done unit → blocked with status message | |
| 10.7 | Add Spare Part row → select a model → part dropdown loads from BOM | |
| 10.8 | ⭐ Select "⚙ General / No Specific Model" → part dropdown loads General Parts (Battery etc.) | |
| 10.9 | Location dropdown loads after part selected (shows qty in stock) | |
| 10.10 | ⭐ NO separate "Add Battery" button exists (battery is via General) | |
| 10.11 | Remove a scooter/part row works | |
| 10.12 | Confirm with unverified scooter → blocked | |
| 10.13 | Confirm with no scooters AND no parts → blocked | |
| 10.14 | Valid dispatch → success, appears in log | |

### 10b. Dispatch log
| # | Test | Y/N |
|---|------|-----|
| 10.15 | Log table loads (date, dealer, scooter count, part count, notes) | |
| 10.16 | Filter by dealer works | |
| 10.17 | Filter by date range works | |
| 10.18 | Clear resets filters | |
| 10.19 | "▶ View" opens detail tab with scooter + part lists | |
| 10.20 | Close detail tab works | |
| 10.21 | Delete dispatch → confirm → scooters revert to pdi_done | |
| 10.22 | Stat cards update after create/delete | |
| 10.23 | After dispatch, the scooter shows as delivered on the Dealers screen | |

---

## 11. Spare Parts

### 11a. Dispatch Log tab
| # | Test | Y/N |
|---|------|-----|
| 11.1 | Table loads (date, dealer, part, qty, location, notes, code) | |
| 11.2 | Search by part name works | |
| 11.3 | ⭐ Search by model name works (e.g. "BirdyGo") | |
| 11.4 | ⭐ Search by colour works (e.g. "Red") | |
| 11.5 | Filter by dealer works | |
| 11.6 | Filter by date range works | |
| 11.7 | Clear resets all | |
| 11.8 | Stat cards: Total Qty, Unique Parts, Dealers Served populate | |

### 11b. By Dealer tab
| # | Test | Y/N |
|---|------|-----|
| 11.9 | Table loads (dealer blue/underlined, code, unique parts, total qty, last dispatch) | |
| 11.10 | Click dealer name → opens dialog of all parts for that dealer | |
| 11.11 | Dialog shows 6 columns (Date, Part, Qty, Location, Notes, Dispatch Note) | |

---

## 12. Damage Log

### 12a. Stat cards
| # | Test | Y/N |
|---|------|-----|
| 12.1 | ⭐ "Damaged Parts Qty" shows a number (not "—") | |
| 12.2 | ⭐ "After Sale Events" shows a number (not "—") | |

### 12b. Before Sale tab
| # | Test | Y/N |
|---|------|-----|
| 12.3 | Table loads (date, part, SKU, type, qty, notes, reporter) | |
| 12.4 | Search by part name works | |
| 12.5 | ⭐ Search by model name works | |
| 12.6 | ⭐ Search by colour works | |
| 12.7 | Date range filter works | |
| 12.8 | Clear resets | |

### 12c. After Sale tab ⭐
| # | Test | Y/N |
|---|------|-----|
| 12.9 | Table loads (date, serial, model, stage, part/damage, notes, reporter) | |
| 12.10 | ⭐ Search bar is present | |
| 12.11 | Search by part/damage works | |
| 12.12 | ⭐ Search by model works | |
| 12.13 | Search by serial number works | |
| 12.14 | ⭐ Search by colour works | |
| 12.15 | Clear resets and reloads | |
| 12.16 | ⭐ Spare-part damage rows show "🔧 Spare Part" instead of a serial number | |
| 12.17 | Stage shows "During Transit" / "After Sale" with correct colour | |

---

## 13. Reports

### 13a. General
| # | Test | Y/N |
|---|------|-----|
| 13.1 | All tabs open without crashing | |
| 13.2 | ⭐ Table text is visible (not white-on-white) | |
| 13.3 | ⭐ Date filter fields are visible and pre-filled | |
| 13.4 | ⭐ Switching tabs auto-refreshes data | |

### 13b. Production tab
| # | Test | Y/N |
|---|------|-----|
| 13.5 | ⭐ Opens without error (no `damaged_quantity` crash) | |
| 13.6 | Shows assembly jobs (model, qty, date, status) | |
| 13.7 | Date filter works | |

### 13c. Dispatch tab
| # | Test | Y/N |
|---|------|-----|
| 13.8 | Shows dispatch records | |
| 13.9 | Date filter works | |

### 13d. PDI tab
| # | Test | Y/N |
|---|------|-----|
| 13.10 | Shows PDI records | |
| 13.11 | Date filter works | |

### 13e. Inventory tab — Max Buildable ⭐
| # | Test | Y/N |
|---|------|-----|
| 13.12 | ⭐ Shows one row per model with a BOM (no "No BOM defined" for valid models) | |
| 13.13 | Max Buildable count = min(stock ÷ qty needed) across BOM | |
| 13.14 | ⭐ Two models with different SKUs show DIFFERENT buildable counts | |
| 13.15 | Bottleneck part shown correctly | |
| 13.16 | Severity colours: red <5, orange <20, green ≥20 | |

---

## 14. User Management

| # | Test | Y/N |
|---|------|-----|
| 14.1 | User list loads | |
| 14.2 | Add user (superadmin) — appears | |
| 14.3 | Edit user (name/role) — saves | |
| 14.4 | Deactivate user — cannot log in afterward | |
| 14.5 | Reactivate user — can log in again | |
| 14.6 | Cannot create duplicate username | |

---

## 15. Cross-Cutting / Edge Cases

| # | Test | Y/N |
|---|------|-----|
| 15.1 | No white-on-white invisible text in ANY table | |
| 15.2 | All action menus close after a selection (none stuck open) | |
| 15.3 | Invalid form input shows a validation message, nothing saved | |
| 15.4 | Large tables scroll smoothly | |
| 15.5 | Server restart mid-session → app shows clean error, recovers on retry | |
| 15.6 | Date fields across all screens render and accept input | |
| 15.7 | Switching between every sidebar screen works without crash | |

---

### Summary
Total checks: count your **N** answers. Anything marked **N** → note the screen + number and report it for a fix.
