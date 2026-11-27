"""Enable `python3 -m storyreel <command>` without requiring installation."""

import sys
from storyreel.cli import main

if __name__ == "__main__":
    sys.exit(main())
