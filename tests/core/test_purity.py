"""The rules engine must stay free of I/O, async and GUI code.

This is the property that makes the engine unit-testable, replayable, and cheap
for a future AI player to simulate by deep-copying and rolling out. If any of
these modules leaks in, that all breaks - so it is asserted, not assumed.
"""

from __future__ import annotations

import subprocess
import sys

FORBIDDEN = ("asyncio", "socket", "PyQt6", "fastapi", "uvicorn", "starlette")


def test_importing_the_engine_pulls_in_no_io_or_gui_modules() -> None:
    # Run in a clean interpreter: the test session itself has already imported
    # plenty of these, so checking sys.modules in-process proves nothing.
    code = (
        "import sys\n"
        "import jwies_core, jwies_core.engine, jwies_core.scoring, jwies_core.contracts\n"
        f"leaked = [name for name in {FORBIDDEN!r} if name in sys.modules]\n"
        "print(','.join(leaked))\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    )
    leaked = result.stdout.strip()
    assert not leaked, f"jwies_core mag deze modules niet binnentrekken: {leaked}"
