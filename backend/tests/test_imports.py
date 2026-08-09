"""Import-smoke test: every module under app/ must import cleanly, with
no ImportError/circular-import surprises. Cheap insurance for the
app/db/models package split and the app/ml_core/evaluation move -- catches
a missed re-export or import-order mistake immediately, without needing
to exercise any actual behavior. Auto-discovers modules (pkgutil) rather
than a hardcoded list, so it doesn't go stale as the codebase grows.
"""
import importlib
import pkgutil

import app


def _all_module_names(package) -> list:
    return [info.name for info in pkgutil.walk_packages(package.__path__, prefix=package.__name__ + ".")]


def test_every_app_module_imports_cleanly():
    modules = _all_module_names(app)
    assert len(modules) > 20  # sanity check the walk actually found the app

    failures = {}
    for name in modules:
        try:
            importlib.import_module(name)
        except Exception as exc:  # noqa: BLE001 -- collect every failure, not just the first
            failures[name] = repr(exc)

    assert not failures, f"Modules failed to import cleanly: {failures}"
