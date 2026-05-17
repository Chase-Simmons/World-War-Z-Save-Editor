"""Top-level entry point used by PyInstaller to build the standalone .exe.

`python -m wwz_save_editor` is the canonical way to run from source — it
executes wwz_save_editor/__main__.py with the package context that
relative imports need.

PyInstaller, however, treats __main__.py as a top-level script and the
relative `from .app import main` blows up. This launcher gives PyInstaller
a script at the project root that absolute-imports the package the same
way an external caller would.
"""
from wwz_save_editor.app import main

if __name__ == "__main__":
    main()
