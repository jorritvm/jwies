"""
Print lines of code per package, plus tests, scripts, and totals.
Run from project root dir.
"""

import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
EXTENSIONS = ("*.py", "*.md", "*.js", ".md")
EXCLUDE_DIR_PREFIXES = (".venv",)
EXCLUDE_DIR_NAMES = {"__pycache__"}

docs_path = ROOT / "docs"
scripts_path = ROOT / "scripts"

src_path = {
    "jwies_server" : ROOT / "jwies-server" / "jwies_server",
    "jwies_core" : ROOT / "jwies-server" / "jwies_core",
    "jwies_qt" : ROOT / "jwies-qt-client" / "jwies_qt_client",
    "jwies_web" : ROOT / "jwies-web-client" / "jwies_web_client",
}

tests_path = {
    "jwies_server + core" : ROOT / "jwies-server" / "tests",
    "jwies_qt" : ROOT / "jwies-qt-client" / "tests",
    "jwies_web" : ROOT / "jwies-web-client" / "tests",
    "integration_tests" : ROOT / "tests",
}

def _is_excluded(path: pathlib.Path) -> bool:
    return any(
        part in EXCLUDE_DIR_NAMES or part.startswith(EXCLUDE_DIR_PREFIXES)
        for part in path.parts
    )


def count_loc(path: pathlib.Path) -> int:
    total = 0
    for pattern in EXTENSIONS:
        for file in path.rglob(pattern):
            if _is_excluded(file):
                continue
            with open(file, encoding="utf-8") as handle:
                total += sum(1 for _ in handle)
    return total


COMPONENTS = ("jwies-server", "jwies-qt-client", "jwies-web-client", "tests")


def main() -> None:
    # Each component is a fully independent uv project with its own tests/
    # nested inside it, rather than one shared top-level tests/ tree.
    src_loc = {
        key: count_loc(value) for key, value in src_path.items() if value.is_dir()
    }
    tests_loc = {
        key: count_loc(value) for key, value in tests_path.items() if value.is_dir()
    }
    scripts_loc = count_loc(scripts_path)
    docs_loc = count_loc(docs_path)

    src_sum = sum(src_loc.values())
    tests_sum = sum(tests_loc.values())

    code_sum = src_sum + scripts_loc + tests_sum

    print("-----------------------------------")
    print("Source:")
    for name, loc in src_loc.items():
        print(f"  {name:<20} {loc:>6}")
    print("  + --------------------------------")
    print(f"  {'sum':<20} {src_sum:>6}")

    print("Tests:")
    for name, loc in tests_loc.items():
        print(f"  {name:<20} {loc:>6}")
    print("  + -------------------------------")
    print(f"  {'sum':<20} {tests_sum:>6}")
    print(f"Scripts: {scripts_loc:>6}")
    print("+ ---------------------------------")
    print(f"Sum of code:   {code_sum:>6}")
    print(f"Documentation:   {docs_loc:>6}")
    print("-----------------------------------")


if __name__ == "__main__":
    main()
