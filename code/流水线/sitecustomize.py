from __future__ import annotations

import os
from pathlib import Path


def _install_svg_export_hook() -> None:
    if os.environ.get("GUI_EXPORT_SVG") != "1":
        return

    try:
        from matplotlib.figure import Figure
    except Exception:
        return

    original_savefig = Figure.savefig
    guard_name = "_gui_svg_export_guard"

    if getattr(Figure.savefig, "__name__", "") == "_patched_savefig":
        return

    def _patched_savefig(self, fname, *args, **kwargs):
        result = original_savefig(self, fname, *args, **kwargs)

        if getattr(self, guard_name, False):
            return result

        try:
            output_path = Path(fname)
        except TypeError:
            return result

        if output_path.suffix.lower() != ".png":
            return result

        svg_path = output_path.with_suffix(".svg")
        try:
            setattr(self, guard_name, True)
            original_savefig(self, svg_path, *args, **kwargs)
        except Exception:
            pass
        finally:
            setattr(self, guard_name, False)
        return result

    Figure.savefig = _patched_savefig


_install_svg_export_hook()
