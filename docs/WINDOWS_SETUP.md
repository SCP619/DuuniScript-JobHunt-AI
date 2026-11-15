# DuuniScript — Windows 11 Setup Guide

## 1. Laptop-only baseline

The complete application can run on the laptop:
- 32 GB system RAM.
- NVIDIA RTX 2070, 8 GB VRAM.
- Windows 11.

The desktop PC is optional. Do not configure network inference until the laptop-only system works.

## 2. Install tools

Install Git for Windows, [uv](https://docs.astral.sh/uv/) (it provides Python 3.11), Node.js LTS
and current NVIDIA drivers. Ollama is optional (local AI).

WSL and Docker are not required.

## 3. Get the code

1. `git clone https://github.com/SCP619/DuuniScript-JobHunt-AI.git`
2. In the cloned folder: `powershell -ExecutionPolicy Bypass -File scripts\setup_new_pc.ps1`
   (details and options in section 12).
3. Start DuuniScript from the Desktop shortcut.

## 4. GitHub

One repository holds the backend (`backend/`), the frontend (`frontend/`), the API contract,
docs and scripts. GitHub holds code only; your data never goes there (section 9).

## 5. Paths

Repository example: `C:\\Users\\<WindowsUser>\\Projects\\DuuniScript`

Private data default: `%LOCALAPPDATA%\\DuuniScript`

Do not put private data inside the repository.

## 6. Backend environment

After the project defines its dependency configuration, a typical PowerShell setup is:

```powershell
Set-Location "C:\\Users\\<WindowsUser>\\Projects\\DuuniScript"
py -m venv .venv
.\\.venv\\Scripts\\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

The final install command must match the actual `pyproject.toml`. Do not run it before that file exists.

If activation is blocked, use a narrowly scoped current-user execution policy or invoke the virtual environment's Python directly. Do not weaken system-wide security unnecessarily.

## 7. Local AI on RTX 2070

Start with one 7B–8B instruction model in 4-bit quantization and benchmark it. Eight GB VRAM does not guarantee every model/context configuration will fit fully in GPU memory. Use a smaller model, shorter context or CPU offload if necessary.

Install one runtime first: Ollama or llama.cpp. Keep model weights and caches outside Git. Check model license, Finnish/English quality, JSON validity, memory and speed.

A multilingual embedding model can be added after the basic inference path works. Avoid adding a reranker initially.

## 8. Browser automation and scheduling

Add Playwright only for a documented, permitted workflow. Use dedicated test profiles and synthetic accounts. Never commit cookies or browser authentication state.

Start with APScheduler inside the backend. Prevent overlapping scans. Consider Windows Task Scheduler only if scans must run while the backend is closed; do not schedule the same scan in both places.

## 9. Private data and backups

Use `%LOCALAPPDATA%\\DuuniScript` and configure `APP_DATA_DIR` only when needed.

Back up SQLite, documents and application packages. Keep backups outside Git and test restoration. Do not use a synchronized cloud folder as the live SQLite database.

## 10. First-run checklist

- [ ] Repository cloned and `scripts\setup_new_pc.ps1` run.
- [ ] `.gitignore` excludes private data.
- [ ] `.env` is untracked.
- [ ] Backend binds to loopback.
- [ ] SQLite is outside Git.
- [ ] Tests pass.
- [ ] Backup/restore documented.
- [ ] No personal data committed.

## 11. Starting DuuniScript

- Double-click **DuuniScript** on the Desktop or in the Start menu (made by
  `scripts\install_shortcuts.ps1`), or `Start DuuniScript.cmd` in the repository folder. It
  starts what is not running and opens http://127.0.0.1:8080. **Stop DuuniScript** stops it.
- `scripts\install_autostart.ps1` starts it in the background at Windows sign-in (`-Remove` undoes it).

## 12. Using DuuniScript on another PC

Code travels through GitHub; your data never does. On the new PC:

1. Install Git, Node.js LTS and uv; optionally Ollama (local AI).
2. Clone the repository (`git clone https://github.com/SCP619/DuuniScript-JobHunt-AI.git`); the backend is
   in `backend\`, the frontend in `frontend\`.
3. On the old PC make a backup (Settings > Backups) and copy the zip to the new PC privately
   (USB stick or your own cloud drive; it contains your CV, facts and applications).
4. Run, in the backend folder:
   `powershell -ExecutionPolicy Bypass -File scripts\setup_new_pc.ps1 -Backup <zip> [-GoogleClientFile <json>] [-Autostart]`
5. Start DuuniScript and sign in with your passphrase (it is in the backup).
6. Reconnect Gmail / UTU mail in the app: sign-in tokens stay in each PC's Windows Credential
   Manager and are never in backups.

Use one PC as the main one. Each PC has its own database; to switch, make a backup on one and
restore it on the other (`scripts
estore_backup.py <zip> --replace` keeps the old data aside).
Do not run two PCs on one shared database file in a synced folder.
