"""Session-wide test safety.

Settings default CREDENTIALS_DIR to data/private, the server's REAL store of connected-account
tokens and imported history. Point every test run at a throwaway folder instead, so tests can
never read, overwrite or delete a developer's real Monzo/Trading212 credentials.
"""

import os
import shutil
import tempfile

_TEST_CREDENTIALS_DIR = tempfile.mkdtemp(prefix="lifeline-test-creds-")


def pytest_configure() -> None:
    os.environ["CREDENTIALS_DIR"] = _TEST_CREDENTIALS_DIR


def pytest_unconfigure() -> None:
    shutil.rmtree(_TEST_CREDENTIALS_DIR, ignore_errors=True)
