"""Update preview cache tokens without platform-specific sed or text re-encoding."""

import argparse
import os
import re
import stat
from datetime import datetime
from pathlib import Path


def stamp_versions(html: bytes, version: str) -> bytes:
    """Replace existing alphanumeric version tokens, preserving all other bytes.

    Raise ValueError for a token outside the HTML cache-token alphabet.
    """
    if re.fullmatch(r"[0-9A-Za-z]+", version) is None:
        raise ValueError("preview version must contain only ASCII letters and digits")
    return re.sub(rb"\?v=[0-9A-Za-z]+", b"?v=" + version.encode("ascii"), html)


def main() -> None:
    """Stamp top-level HTML files in the chosen preview; refuse linked output files."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    pages = sorted(args.directory.glob("*.html"))
    if not args.directory.is_dir():
        parser.error("preview directory does not exist")
    if any(page.is_symlink() for page in pages):
        parser.error("preview HTML files must not be symbolic links")
    version = datetime.now().strftime("%Y%m%d%H%M")
    for page in pages:
        # Keep the checked file handle for both reading and rewriting, even if its name changes.
        fd = os.open(page, os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, "r+b") as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                parser.error("preview HTML files must be regular files")
            stamped = stamp_versions(stream.read(), version)
            stream.seek(0)
            stream.write(stamped)
            stream.truncate()
    print(f"preview stamped ?v={version}")


if __name__ == "__main__":
    main()
