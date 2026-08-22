#!/usr/bin/env python3
"""Deterministic Hax stand-in; never contacts a provider or reads credentials."""
from __future__ import annotations

import os
import sys

if "--version" in sys.argv:
    print(os.environ.get("FAKE_HAX_VERSION", "hax v0.3.0"))
    raise SystemExit(0)

if os.environ.get("FAKE_HAX_RESULT") == "429":
    print("HTTP 429 quota exhausted", file=sys.stderr)
    raise SystemExit(1)

if "-p" in sys.argv:
    print("FAKE_HAX_ONESHOT_OK")
else:
    print("READY >")
