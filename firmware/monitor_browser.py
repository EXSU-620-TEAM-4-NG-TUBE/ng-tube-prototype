"""Start the Windows browser monitor from the firmware folder."""

import runpy
import sys
from pathlib import Path

if __name__ == "__main__":
    monitor = Path(__file__).resolve().parents[1] / "software" / "browser_monitor"
    sys.path.insert(0, str(monitor))
    runpy.run_path(str(monitor / "service.py"), run_name="__main__")
