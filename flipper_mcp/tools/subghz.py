"""Sub-GHz radio tools.

A dedicated home for Sub-GHz work. `flipper_subghz_tx` replays a saved .sub
capture; receiving is done through `flipper_listen('subghz rx ...')`. New
Sub-GHz helpers (frequency presets, capture parsing, etc.) belong here.
"""

from ..app import mcp
from ..transport import Flipper


@mcp.tool()
def flipper_subghz_tx(path: str, frequency: int = 433920000) -> str:
    """Transmit a saved Sub-GHz .sub file at the given frequency (Hz). Transmit
    only on bands legal where you are, to devices you own (e.g. replay your own
    garage/gate remote capture)."""
    with Flipper() as f:
        return f.cli(f'subghz tx_from_file "{path}" {frequency}', 30)
