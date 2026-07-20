# Developer documentation

## Dependency management with uv
```shell
uv add <package>        # add a runtime dependency to pyproject.toml
uv add --dev <package>  # add a development dependency
uv remove <package>     # remove a dependency
uv lock --upgrade       # upgrade the lockfile to the latest allowed versions
uv sync                 # sync the .venv with pyproject.toml/uv.lock
```

## Regenerating the Qt Designer UI files
The `.ui` files in `src/ui/` are loaded at runtime with `uic.loadUi`, but they can
also be converted to python modules:


## Repo layout
```
config/     runtime configuration (controller.ini, player.ini)
docs/       architecture notes, screenshots, style guide
resources/  images and the SVG card deck
scripts/    developer utility scripts
src/        application source code (imports resolve relative to src/)
src/ui/     Qt Designer .ui files and their generated .py counterparts
```
