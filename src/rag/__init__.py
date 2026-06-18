# pysqlite3 patch — only needed on Python <= 3.12 with an old bundled SQLite.
# Python 3.13+ ships SQLite >= 3.35 natively, so this is a no-op on modern builds.
import sys

try:
    import pysqlite3  # type: ignore
    sys.modules["sqlite3"] = sys.modules.pop("pysqlite3")
except ImportError:
    pass  # Not installed or not needed — safe to skip
