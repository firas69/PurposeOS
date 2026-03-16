"""
adctl.py — PurposeOS CLI entry point

The CLI is now implemented in purposeos/cli/. This file exists solely
to satisfy the pyproject.toml entry point:

    adctl = "purposeos.adctl:main"

and the entry-point wrapper at ~/.local/bin/adctl:

    from purposeos.adctl import main
    main()
"""

from purposeos.cli.parser import main  # noqa: F401
