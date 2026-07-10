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
