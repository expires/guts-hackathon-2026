"""Atomic 0600 JSON writer shared by the credential store and the Monzo history store."""

import json
import os
from pathlib import Path
from typing import Any


def write_private_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    tmp = path.with_suffix(".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(json.dumps(payload))
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)
