"""
TenderCheck launcher — run this with:
    python run.py
or double-click in Explorer.

Ensures all dependencies are on sys.path and starts the uvicorn server.
"""
import sys
import os
import subprocess

# Ensure user site-packages are on path (works around some Windows configurations)
import site
user_site = site.getusersitepackages()
if user_site and user_site not in sys.path:
    sys.path.insert(0, user_site)

# Quick dependency check — install inline if anything is missing
REQUIRED = [
    ("sqlalchemy", "sqlalchemy>=2.0"),
    ("fastapi", "fastapi>=0.111"),
    ("uvicorn", "uvicorn[standard]>=0.29"),
    ("jose", "python-jose[cryptography]>=3.3"),
    ("passlib", "passlib[bcrypt]>=1.7"),
    ("multipart", "python-multipart>=0.0.9"),
    ("pdfminer", "pdfminer.six>=20221105"),
    ("sentence_transformers", "sentence-transformers>=2.7"),
]

missing = []
for mod, pkg in REQUIRED:
    try:
        __import__(mod)
    except ImportError:
        missing.append(pkg)

if missing:
    print(f"[launcher] Installing missing packages: {missing}")
    subprocess.check_call([
        sys.executable, "-m", "pip", "install", "--user", *missing
    ])
    # Re-add user site to path after install
    if user_site and user_site not in sys.path:
        sys.path.insert(0, user_site)

# Start uvicorn programmatically
print("[launcher] Starting TenderCheck API on http://127.0.0.1:8000")
print("[launcher] Open frontend/index.html in your browser")
print("[launcher] API docs: http://127.0.0.1:8000/docs")
print("[launcher] Press Ctrl+C to stop\n")

import uvicorn
uvicorn.run(
    "backend.main:app",
    host="127.0.0.1",
    port=8000,
    reload=True,
    reload_dirs=["backend"],
)
