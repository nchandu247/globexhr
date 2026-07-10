"""
Every DocType controller module must be importable.

Catches the class of bug where a relative import resolves inside the module
folder instead of the app package (e.g. `from ...letters import engine`
becoming `globex_hr_letters.hr_letters.letters`). That only explodes on the
live site when Frappe loads the controller during install/migrate — the rest
of the suite imports engine/merger/etc. directly and never touches the
controller modules.
"""
import importlib
import pathlib

import pytest

# .../globex_hr_letters (the app package directory)
APP_PKG = pathlib.Path(__file__).resolve().parents[1]


def _controller_modules():
    mods = []
    for py in sorted(APP_PKG.glob("hr_letters/doctype/*/*.py")):
        if py.name == "__init__.py":
            continue
        rel = py.relative_to(APP_PKG.parent).with_suffix("")
        mods.append(".".join(rel.parts))
    return mods


def test_controller_modules_discovered():
    """Guard against a silent empty glob making the sweep vacuous."""
    assert len(_controller_modules()) >= 4  # 4 doctypes ship with the app


@pytest.mark.parametrize("module_name", _controller_modules())
def test_controller_module_imports(module_name):
    importlib.import_module(module_name)


def test_no_triple_dot_relative_imports():
    """Static sweep of every .py in the app for `from ...`-style imports.

    Three dots from a doctype controller resolve inside the module folder,
    not the app package. Function-level occurrences don't explode at import
    time (the module-import sweep above can't see them), so ban the pattern
    outright — use absolute imports instead.
    """
    offenders = []
    for py in sorted(APP_PKG.rglob("*.py")):
        if "tests" in py.relative_to(APP_PKG).parts:
            continue
        for lineno, line in enumerate(py.read_text(encoding="utf-8").splitlines(), 1):
            if line.lstrip().startswith("from ..."):
                offenders.append(f"{py.relative_to(APP_PKG)}:{lineno}: {line.strip()}")
    assert not offenders, "Triple-dot relative imports found:\n" + "\n".join(offenders)
