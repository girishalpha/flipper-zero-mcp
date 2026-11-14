"""Tool modules, one file per task domain.

Importing this package imports every submodule, and importing a submodule runs
its `@mcp.tool()` decorators, which registers those tools on the shared FastMCP
instance. To add a new domain (nfc, rfid, infrared, gpio, ...), drop a new module
in this folder and add it to `_MODULES`.
"""

from importlib import import_module

_MODULES = (
    "device",
    "storage",
    "gui",
    "apps",
    "survey",
    "knowledge",
    "subghz",
    "badusb",
)

for _name in _MODULES:
    import_module(f"{__name__}.{_name}")
