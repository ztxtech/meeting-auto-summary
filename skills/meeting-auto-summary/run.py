from __future__ import annotations

import sys
from pathlib import Path


def main() -> int:
    skill_dir = Path(__file__).resolve().parent
    sys.path.insert(0, str(skill_dir))

    from scripts.cli import main as cli_main

    return cli_main()


if __name__ == "__main__":
    raise SystemExit(main())
