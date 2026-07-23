#!/usr/bin/env python3
"""SUPERSEDED — legacy FTP deployment for the agenticmarketintel.ai marketing site.

Kept for reference only. The live deploy path is rsync over SSH (alias `ami-web`);
see docs/WEBSITE.md. Do not use this unless SSH is unavailable.

Moved out of `website/` in CR072: it lived inside the deployable docroot, so every
rsync republished it — it was publicly served for months alongside WEBSITE.md and a
stale Archive.zip until CR049 deleted them server-side. Deleting them from the
server without removing them from the source only bought time; the next deploy
would have put them straight back. `website/` now holds deployable content and
nothing else, which is what makes `rsync --delete` safe here.

It carries no password (taken as argv) but does disclose the FTP host and username.

Usage:
  python3 scripts/deploy_ftp_legacy.py YOUR_FTP_PASSWORD
"""

import ftplib
import os
import sys
from pathlib import Path

HOST   = "ftp.agenticmarketintel.ai"  # resolves to 69.57.162.213
PORT   = 21
USER   = "claude@agenticmarketintel.ai"
SITE_DIR = Path(__file__).parent  # this script lives inside website/

def upload_dir(ftp, local_path, remote_path):
    """Recursively upload local_path to remote_path."""
    try:
        ftp.mkd(remote_path)
    except ftplib.error_perm:
        pass  # already exists

    for item in sorted(local_path.iterdir()):
        remote_item = f"{remote_path}/{item.name}"
        if item.is_dir():
            upload_dir(ftp, item, remote_item)
        else:
            print(f"  uploading {item.relative_to(SITE_DIR.parent)}")
            with open(item, "rb") as f:
                ftp.storbinary(f"STOR {remote_item}", f)

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 deploy_ftp.py YOUR_FTP_PASSWORD")
        sys.exit(1)

    password = sys.argv[1]

    print(f"Connecting to {HOST}:{PORT} as {USER} ...")
    ftp = ftplib.FTP()
    ftp.connect(HOST, PORT, timeout=30)
    ftp.login(USER, password)
    ftp.set_pasv(True)

    print("\nFTP root contents (confirming target directory):")
    ftp.retrlines("LIST")

    # Upload to root — cPanel FTP accounts for a domain typically root
    # at public_html for that domain. Confirm above before proceeding.
    target = "/"
    print(f"\nUploading website/ → {target}")
    upload_dir(ftp, SITE_DIR, target.rstrip("/"))

    ftp.quit()
    print("\nDone. Visit https://www.agenticmarketintel.ai to verify.")

if __name__ == "__main__":
    main()
