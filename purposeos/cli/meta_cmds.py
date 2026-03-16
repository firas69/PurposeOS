"""
cli/meta_cmds.py — Package self-management commands

update   — runs update.sh from the recorded source path
uninstall — execs uninstall.sh from the manifest directory
version  — prints the installed package version

The manifest directory (~/.local/share/purposeos/) is written by install.sh
and contains uninstall.sh and a source_path file.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from purposeos.cli._output import CY, B, R, _err, _info


def _manifest_dir() -> Path:
    """Return the path to the install manifest directory."""
    return Path.home() / ".local" / "share" / "purposeos"


def cmd_update(_args) -> None:
    """Run update.sh from the recorded source path."""
    source_path_file = _manifest_dir() / "source_path"
    if not source_path_file.exists():
        _err(
            "Source path not recorded. This happens when the package was installed\n"
            "   without install.sh (e.g. pip install directly).\n"
            f"   To fix: echo /path/to/project > {source_path_file}"
        )
        return

    source_dir = Path(source_path_file.read_text(encoding="utf-8").strip())
    update_sh = source_dir / "update.sh"

    if not update_sh.exists():
        _err(
            f"update.sh not found at {update_sh}\n"
            f"   The source directory may have been moved.\n"
            f"   Update source_path: echo /new/path > {source_path_file}"
        )
        return

    _info(f"Running update from {source_dir}")
    try:
        import subprocess as _sp

        result = _sp.run(["bash", str(update_sh)], cwd=str(source_dir))
        sys.exit(result.returncode)
    except Exception as exc:
        _err(f"Update failed: {exc}")


def cmd_uninstall(_args) -> None:
    """Run uninstall.sh from the manifest directory."""
    uninstall_sh = _manifest_dir() / "uninstall.sh"

    if not uninstall_sh.exists():
        _err(
            f"Uninstaller not found at {uninstall_sh}\n"
            "   It may have been deleted, or the package was not installed via install.sh.\n"
            "   Run uninstall.sh directly from your source tree instead."
        )
        return

    try:
        # os.execv replaces this process with the shell script, preserving
        # stdin so that the interactive y/N prompts work correctly.
        os.execv("/bin/bash", ["/bin/bash", str(uninstall_sh)])
    except Exception as exc:
        _err(f"Failed to launch uninstaller: {exc}")


def cmd_version(_args) -> None:
    """Print the installed version."""
    try:
        import purposeos as _pkg

        version = getattr(_pkg, "__version__", "unknown")
    except Exception:
        version = "unknown"
    print(f"\n  {CY}{B}PurposeOS{R}  v{version}\n")
