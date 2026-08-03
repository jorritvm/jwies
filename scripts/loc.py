"""
Print lines of code per package, plus tests, scripts, and totals.
Run from project root dir.
"""

import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
EXTENSIONS = ("*.py", "*.md", "*.js", ".md")
EXCLUDE_DIR_PREFIXES = (".venv",)
EXCLUDE_DIR_NAMES = {"__pycache__"}


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


def main() -> None:
    packages = {
        pkg.name: count_loc(pkg)
        for pkg in sorted((ROOT / "packages").iterdir())
        if pkg.is_dir()
    }
    tests_loc = count_loc(ROOT / "tests")
    scripts_loc = count_loc(ROOT / "scripts")
    docs_loc = count_loc(ROOT / "docs")

    packages_sum = sum(packages.values())
    grand_total = packages_sum + tests_loc + scripts_loc

    print("Packages:")
    for name, loc in packages.items():
        print(f"  {name:<20} {loc:>6}")
    print(f"  {'sum':<20} {packages_sum:>6}")
    print(f"Tests:   {tests_loc:>6}")
    print(f"Scripts: {scripts_loc:>6}")
    print("------------------------")
    print(f"Total code:   {grand_total:>6}")
    print()
    print(f"Documentation:   {docs_loc:>6}")


if __name__ == "__main__":
    main()
