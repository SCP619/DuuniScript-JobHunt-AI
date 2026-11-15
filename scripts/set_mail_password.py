"""Save the job alert mailbox password in Windows Credential Manager.

Run from the repository root (PowerShell):

    .venv\\Scripts\\python.exe scripts\\set_mail_password.py

For Gmail, use an app password (Google Account > Security > 2-Step Verification >
App passwords), not your normal password. The password is typed without echo, stored only
in Windows Credential Manager under "DuuniScript mailbox", and never written to a file.
Remove it with:  .venv\\Scripts\\python.exe scripts\\set_mail_password.py --remove
"""

from __future__ import annotations

import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.adapters.mailbox import KEYRING_SERVICE, set_password  # noqa: E402
from app.core.config import get_settings  # noqa: E402


def main() -> int:
    user = get_settings().mail_imap_user
    if not user:
        print("Set MAIL_IMAP_USER in the .env file first (the mailbox address).")
        return 1
    if "--remove" in sys.argv:
        import keyring

        try:
            keyring.delete_password(KEYRING_SERVICE, user)
        except keyring.errors.PasswordDeleteError:
            print("No saved password for", user)
            return 0
        print("Removed the saved password for", user)
        return 0
    password = getpass.getpass(f"App password for {user} (input is hidden): ").replace(" ", "")
    if not password:
        print("Nothing saved.")
        return 1
    set_password(user, password)
    print("Saved in Windows Credential Manager. Restart the DuuniScript API to start checking alerts.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
