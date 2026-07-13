"""The chapter 00 smoke test.

It does almost nothing on purpose. Its only job is to prove that the package
imports and the test runner, coverage gate, linter, and type checker are all
wired up correctly before we write any real code.
"""

import chainidx


def test_package_imports_and_has_a_version() -> None:
    assert chainidx.__version__ == "0.1.0"
