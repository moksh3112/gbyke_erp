# G-Byke ERP — Maintenance Guide

## Remote Access
- AnyDesk ID: [WRITE YOUR CAMERA PC'S ANYDESK ID HERE]
- AnyDesk Password: [stored securely, not here]
- Camera PC local IP: 192.168.1.XXX [fill in after setting static IP]

## Pushing an update from college

### Step 1 — Make your changes on your dev laptop
### Step 2 — Bump the version number
- Edit `version.py` → change VERSION = "1.0.1" (or whatever)

### Step 3 — Push to GitHub
git add .
git commit -m "describe what you changed"
git push origin main

### Step 4 — Update the camera PC (two options)

**Option A — Someone at factory runs it:**
- Tell them to double-click `update_server.bat` on the camera PC desktop
- Done in 2 minutes, no technical knowledge needed

**Option B — You do it remotely:**
- Open AnyDesk, connect to camera PC
- Double-click `update_server.bat`
- Watch it complete, close AnyDesk

### Step 5 — Update each laptop
- Each laptop user double-clicks `update_client.bat`
- Or you remote in via AnyDesk and do it yourself

## Database backup location
- Automatic backups: C:\gbyke_erp\backups\ (set up on Day 13)
- Manual backup command:
pg_dump -U postgres gbyke_erp > backup.sql

## If the server crashes
- Double-click `start_server.bat` on the camera PC desktop
- If that fails, restart the camera PC — server auto-starts on boot

## Admin credentials
- Username: admin
- Password: [stored securely, not here — change after first login]

## GitHub repository
- https://github.com/moksh3112/gbyke_erp