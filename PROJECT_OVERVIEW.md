# G-Byke ERP — Project Overview & Deployment Summary

> Handoff document describing the system, every file, the auto-update mechanism,
> deployment model, known constraints, and current state. Upload this to get a
> further action plan.

---

## 1. What the system is

A factory ERP for an e-scooter (G-Byke) manufacturer.

**Architecture — two separate programs talking over HTTP on a LAN:**

| Part | Tech | Runs where |
|------|------|-----------|
| **Backend / server** | FastAPI + Uvicorn + SQLAlchemy + PostgreSQL | ONE PC (the "camera PC") |
| **Desktop client** | PyQt6 (packaged to a Windows .exe) | Each staff laptop |

- Client ↔ server communication: REST/JSON over `http://<server-ip>:8000`, JWT bearer auth.
- The client imports **nothing** from the backend — fully decoupled.
- Database: PostgreSQL on the server PC only. Laptops need no Python and no DB.

**Repo:** https://github.com/moksh3112/gbyke_erp (branch `main`)

---

## 2. Deployment model

- **Camera PC = server.** Runs PostgreSQL + the FastAPI server (`uvicorn ... --host 0.0.0.0 --port 8000`), and also builds + hosts the client .exe for auto-update.
- **Laptops = clients.** Each runs `GByke ERP.exe` from a self-contained folder with a `.env` next to it pointing at the server's LAN IP.
- Currently being tested with the developer's laptop acting as the server (IP `192.168.29.49`).

---

## 3. Auto-update system (the core of recent work)

**Goal:** push code from anywhere → server self-updates → laptops update with one click.

**Full chain:**
```
Developer edits code + bumps version.py → git push to GitHub
      ↓
Camera PC checks GitHub every 5 min (auto_update_check.bat via Task Scheduler)
      ↓ new commit found
update_server.bat: git pull → pip install → pyinstaller rebuild → restart server
      ↓
Server now serves new exe at GET /download/client and reports new /version
      ↓
Laptop app: startup check (forced dialog) OR mid-session poll every 5 min (banner)
      ↓ user clicks "Update Now"
Downloads zip → kills all app instances → copies new files → relaunches as new version
```

`version.py` is the **single source of truth** for the version and the trigger laptops
compare against. It MUST be bumped on every release or laptops won't prompt.

---

## 4. Every file — created and modified

### Created
| File | Purpose |
|------|---------|
| `app/routers/updates.py` | Serves the client build. `GET /download/client` zips the `dist/GByke ERP/` folder and returns it. |
| `desktop/updater.py` | `UpdateDialog` (forced, blocking). Downloads the zip with a progress bar, extracts to temp, writes a `.bat` that kills all app instances + robocopies new files over the app folder + relaunches. Calls `os._exit(0)` to force-quit. |
| `desktop/update_notifier.py` | `UpdatePoller` QThread. After login, polls `/version` every 5 min; on mismatch emits a signal (fires once) → shows a non-blocking amber banner. |
| `gbyke_erp.spec` | PyInstaller **onedir** build spec for the client exe. |
| `auto_update_check.bat` | Run by Task Scheduler every 5 min on the server. `git fetch`, compares local vs `origin/main`, and if different calls `update_server.bat`. |
| `.env.example` | Template documenting every env key (no secrets). |

### Modified
| File | Change |
|------|--------|
| `app/main.py` | Registered the `updates` router. |
| `main.py` (desktop launcher) | `_check_for_update()` runs before the window opens; shows forced dialog if frozen and server has a newer version. |
| `desktop/app.py` | Starts `UpdatePoller` after login; `_show_update_banner()` inserts the amber banner. |
| `desktop/utils/api_client.py` | `SERVER_IP`/`SERVER_PORT` read from `.env`; `.env` is loaded from **beside the exe** (frozen) or project root (dev). |
| `update_server.bat` | Added a step to rebuild the client exe with PyInstaller after `git pull`. |
| `version.py` | Single source of truth. Currently `1.5.0` (bumped during testing). |
| `.gitignore` | Added `!gbyke_erp.spec` so the build spec is tracked (server needs it). |

### Pre-existing relevant files
| File | Purpose |
|------|---------|
| `start_server.bat` | Starts uvicorn on `0.0.0.0:8000`. |
| `update_client.bat` | Older git-pull-based client updater (largely superseded by the in-app auto-update). |
| `requirements.txt` | Python deps (FastAPI, PyQt6, SQLAlchemy, psycopg2-binary, etc.). |
| `.env` | Secrets — DB creds, JWT secret, admin seed. **Gitignored, never uploaded.** |
| `app/database.py`, `app/core/config.py` | DB connection + settings, read from `.env`. |
| `app/routers/*` | 12 feature routers: auth, inventory, models, users, manufacturing, pdi, warehouses, dealers, shipments, spare_parts, damage_log, reports. |
| `desktop/screens/*` | 16 PyQt6 screens wired into the sidebar. |

---

## 5. Build & packaging — hard-won constraints

- **Must use Python 3.12** for the build venv. **Python 3.14 does NOT work** with PyInstaller (fails to load `python312.dll` / DLL errors).
- **Must use onedir mode, not onefile.** Onefile extracts to a `_MEI` temp folder and reliably throws "Failed to load Python DLL". Onedir keeps `python312.dll` in `_internal/` beside the exe — no temp extraction, no error. The whole `dist/GByke ERP/` folder is the app; distribute the **entire folder**, not just the .exe.
- Build command: `pyinstaller gbyke_erp.spec --clean --noconfirm`
- `dist/` and `build/` are gitignored; the server rebuilds the exe locally on each update.

### Self-update gotchas already solved
1. **Kill by image name, not PID.** The updater bat uses `taskkill /F /IM "GByke ERP.exe"`. Any second running instance from the same folder keeps `_internal/*.dll` locked, so killing one PID isn't enough; robocopy then fails with "being used by another process".
2. **No wait-loop in the bat** (an earlier `tasklist | find <pid>` loop hung forever). Just `timeout` → `taskkill /F /IM` → `robocopy /R:5 /W:1` → relaunch.
3. **`os._exit(0)`**, not `sys.exit()` — the Qt modal event loop swallows `sys.exit`.
4. The client's `.env` (with the server IP) survives updates because robocopy `/E` doesn't delete dest-only files.

---

## 6. Configuration (.env keys)

Server PC uses all keys; laptops only need the SERVER_ ones.
```
DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD   # server: PostgreSQL
SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES # server: JWT
SERVER_HOST, SERVER_PORT                           # server: uvicorn bind
SERVER_IP                                          # client: server's LAN IP  ← laptops set this
ADMIN_USERNAME, ADMIN_PASSWORD, ADMIN_FULL_NAME    # server: first-run admin seed
```
On each laptop, the `.env` next to the exe only needs:
```
SERVER_IP=<server LAN ip>
SERVER_PORT=8000
```

---

## 7. Current state / what's verified

- ✅ Client exe builds (Python 3.12, onedir) and launches with no DLL errors.
- ✅ LAN client→server works (tested: dev laptop as server `192.168.29.49`, app on a second laptop).
- ✅ Full self-update verified end-to-end: forced dialog → download → kill → copy → relaunch as new version.
- ✅ Code pushed to GitHub.
- ✅ Client reads `.env` from beside the exe.

---

## 8. Open items / not yet done (candidates for the action plan)

1. **Camera PC one-time setup not yet performed:** clone repo, Python 3.12 venv, `pip install` + `pip install pyinstaller`, create the `gbyke_erp` PostgreSQL DB, run migrations/seed admin.
2. **Git auth on camera PC:** confirm whether the GitHub repo is public or private. If private, the camera PC needs stored credentials (PAT) or `git pull` silently fails — breaking the whole auto-update chain.
3. **Task Scheduler jobs (two of them):**
   - `auto_update_check.bat` every 5 min (the updater).
   - Auto-start the server on boot (for power outages) + BIOS "Power On after AC loss".
4. **Server should run headless/auto-restart** reliably (currently launched via a console `start_server.bat`).
5. **Static IP for the camera PC** so the laptops' `.env` never breaks when DHCP changes the IP.
6. **`version.py` is at `1.5.0`** from testing — set a real starting version before go-live.
7. **Security review:** `.env` holds a plaintext DB password and admin creds; fine for LAN but worth hardening. CORS is not configured (not needed for the PyQt client, but would be for any browser client).
8. **Firewall:** inbound TCP 8000 must be allowed on the server (one-time admin command).
9. Consider whether the old `update_client.bat` (git-based) should be removed now that in-app auto-update exists.

---

## 9. Key commands reference

```bat
:: Build the client exe (server PC, Python 3.12 venv)
pyinstaller gbyke_erp.spec --clean --noconfirm

:: Start the server
start_server.bat        ::  uvicorn app.main:app --host 0.0.0.0 --port 8000

:: Release from anywhere
::   1) bump version.py   2) git commit   3) git push
:: Camera PC auto-pulls within 5 min and rebuilds; laptops prompt to update.

:: Open firewall (admin PowerShell, one time, on server)
New-NetFirewallRule -DisplayName "GByke ERP Server" -Direction Inbound -Protocol TCP -LocalPort 8000 -Action Allow
```
