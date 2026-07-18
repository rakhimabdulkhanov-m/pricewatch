"""Minimal .env loader — sets os.environ for keys not already present.

Called once at run.py entry for local development.
Does NOT use python-dotenv or any third-party library.
"""

import os
from pathlib import Path


def load_dotenv(path: str | Path = ".env") -> None:
    """Read *path* and export KEY=VALUE pairs into os.environ.

    Skips blank lines, comment lines (#), and keys already set in the env.
    """
    p = Path(path)
    if not p.exists():
        return
    with p.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()
            if key and key not in os.environ:
                os.environ[key] = value
