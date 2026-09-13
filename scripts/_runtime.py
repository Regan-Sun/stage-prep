"""Optional installation-local dependencies, excluded from portable packages."""
import sys
from pathlib import Path

local = Path(__file__).resolve().parents[1] / '.runtime'
if local.is_dir():
    sys.path.insert(0, str(local))
