"""Load and atomically save the local JSON store (contracts/store-schema.md, research R6)."""

import json
import os
from pathlib import Path

from pydantic import ValidationError

from applytrail.errors import StoreUnreadable
from applytrail.models import Store


def load(path: Path) -> Store:
    """Return the saved store, or an empty one if the file does not exist yet."""
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        return Store.empty()
    except OSError as err:
        raise StoreUnreadable(path) from err
    try:
        return Store.model_validate(json.loads(raw))
    except (ValueError, ValidationError) as err:
        raise StoreUnreadable(path) from err


def save(store: Store, path: Path) -> None:
    """Write to a temp file in the same folder, fsync, then rename over the store.

    Refuses to write an invalid store, and refuses to replace an existing file that does not
    load (raises StoreUnreadable), so a damaged store is left for the user to inspect.
    """
    data = Store.model_validate(store.model_dump(mode="json")).model_dump(mode="json")
    text = json.dumps(data, indent=2, sort_keys=True) + "\n"
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(path.parent, 0o700)
    load(path)
    write_private(path, text)


def write_private(path: Path, text: str) -> None:
    """Atomically replace `path` with `text` as a new 0600 file (temp file, fsync, rename).

    Also used for the OAuth token. The parent folder must already exist.
    """
    tmp = path.with_name(path.name + ".tmp")
    # A leftover temp file (or a symlink planted there) is removed, never followed.
    tmp.unlink(missing_ok=True)
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
