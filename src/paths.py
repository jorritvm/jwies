# central path resolution: all paths are resolved relative to the project root,
# independent of the current working directory
from pathlib import Path

PROJECT_ROOT: Path = Path(__file__).resolve().parents[1]
SRC_DIR: Path = PROJECT_ROOT / "src"
UI_DIR: Path = SRC_DIR / "ui"
RESOURCES_DIR: Path = PROJECT_ROOT / "resources"
CONFIG_DIR: Path = PROJECT_ROOT / "config"
