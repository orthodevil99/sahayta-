"""Sahayta early-warning pipeline (Wave 3, Agent 7).

Owns the weather → risk → threshold-alert loop:

- ``ingest``     — poll Open-Meteo on a schedule; on ANY failure fall back to
                   the clearly-labeled simulated feed (``weather_source ==
                   "simulated"``).
- ``recompute``  — aggregate the trailing 24 h of samples per district, score
                   with the shared v1 formula (``app.services.risk``), persist
                   ``DistrictRisk`` rows, emit WS ``risk.updated``.
- ``thresholds`` — crossing risk > 70 (advisory) or > 85 (warning) triggers an
                   automatic multilingual broadcast (deduplicated, 24 h).
- ``scheduler``  — asyncio background loop started from the app lifespan.
- ``backtest``   — offline replay of ``data/weather-sample.json`` producing
                   ``BACKTEST_REPORT.md`` (precision/recall of would-have-warned).

Nothing here is ever presented as live when it is simulated: the
``weather_source`` column and the ``/api/*`` responses carry the label, and the
frontend renders the "SIMULATED FEED" badge from it.

Package-name note: this package is deliberately named ``warnings`` (per the
Wave 3 brief: ``backend/warnings/``), which shadows the stdlib ``warnings``
module whenever ``backend/`` is on ``sys.path``. The shim below re-exports the
real stdlib ``warnings`` surface (``warn``, ``filterwarnings``, …) so that
``from warnings import warn`` — used by stdlib modules such as ``random`` —
keeps working. Submodule imports are lazy (PEP 562) so even
``python -m warnings.backtest`` boots cleanly.
"""

# --- stdlib-shadowing shim (must run before any other import in this file) ---
import importlib.util as _ilu
import os as _os
import sys as _sys


def _load_stdlib_warnings():
    stdlib_dir = _os.path.dirname(_os.__file__)  # <python>/lib/python3.x
    path = _os.path.join(stdlib_dir, "warnings.py")
    spec = _ilu.spec_from_file_location("_sahayta_stdlib_warnings", path)
    mod = _ilu.module_from_spec(spec)
    _sys.modules["_sahayta_stdlib_warnings"] = mod
    spec.loader.exec_module(mod)
    return mod


_std_warnings = _load_stdlib_warnings()
for _name in [n for n in dir(_std_warnings) if not n.startswith("__")]:
    globals().setdefault(_name, getattr(_std_warnings, _name))
del _name, _std_warnings, _load_stdlib_warnings, _ilu, _os, _sys
# --- end shim ---


def __getattr__(name: str):
    """Lazy submodule exports (avoids importing httpx on package import)."""
    _exports = {
        "ingest_district": (".ingest", "ingest_district"),
        "ingest_all": (".ingest", "ingest_all"),
        "IngestResult": (".ingest", "IngestResult"),
        "recompute_district": (".recompute", "recompute_district"),
        "recompute_all": (".recompute", "recompute_all"),
        "check_thresholds": (".thresholds", "check_thresholds"),
        "broadcast_threshold_alert": (".thresholds", "broadcast_threshold_alert"),
        "process_crossings": (".thresholds", "process_crossings"),
        "ADVISORY_THRESHOLD": (".thresholds", "ADVISORY_THRESHOLD"),
        "WARNING_THRESHOLD": (".thresholds", "WARNING_THRESHOLD"),
        "run_cycle": (".scheduler", "run_cycle"),
        "start_scheduler": (".scheduler", "start_scheduler"),
        "stop_scheduler": (".scheduler", "stop_scheduler"),
    }
    if name in _exports:
        import importlib

        mod_name, attr = _exports[name]
        mod = importlib.import_module(mod_name, __name__)
        return getattr(mod, attr)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "ADVISORY_THRESHOLD",
    "WARNING_THRESHOLD",
    "IngestResult",
    "broadcast_threshold_alert",
    "check_thresholds",
    "ingest_all",
    "ingest_district",
    "process_crossings",
    "recompute_all",
    "recompute_district",
    "run_cycle",
    "start_scheduler",
    "stop_scheduler",
]
