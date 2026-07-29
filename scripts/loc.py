"""
print loc in this project
run from project root dir
"""

import pathlib


def count_loc():
    total = 0
    for path in pathlib.Path(".").rglob("*.py"):
        if ".venv" not in path.parts:  # skip any file under .venv
            with open(path, encoding="utf-8") as handle:
                total += sum(1 for _ in handle)
    return total


if __name__ == "__main__":
    total = count_loc()
    print(f"LOC: {total}")
