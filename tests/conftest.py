import sys
from pathlib import Path

# Make sure we can import the package without an editable install.
# This adds "<repo_root>/src" to sys.path for the test session.
repo_root = Path(__file__).resolve().parents[1]
src = repo_root / "src"
if str(src) not in sys.path:
    sys.path.insert(0, str(src))
