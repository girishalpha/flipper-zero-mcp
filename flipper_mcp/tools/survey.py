"""Survey tools: index the device and search the SD before a task.

`flipper_index` gives one-call structural context (firmware/radio/SD + an /ext
tree); `flipper_find` locates files by name. Both are call-budgeted so they stay
fast on large SD cards, and both are read-only.
"""

from ..app import mcp
from ..transport import Flipper


@mcp.tool()
def flipper_index(depth: int = 2, max_calls: int = 80) -> str:
    """Survey the device before a task, WITH SUBSTRUCTURE. Returns
    firmware/hardware/region, running app and SD free space, then a tree of /ext
    down to `depth` levels with per-folder file/subdir counts. Folders with many
    subdirs are counted but not expanded; a call budget (max_calls) keeps it fast.
    One call = full structural context. Pass a higher depth for more. Read-only."""
    with Flipper() as f:
        di = {r.split(":")[0].strip(): r.split(":", 1)[1].strip()
              for r in f.cli("device_info", 20).splitlines() if ":" in r}
        L = ["# FLIPPER INDEX",
             "device  : %s  fw %s (%s)  region %s" % (
                 di.get("hardware_name", "?"), di.get("firmware_version", "?"),
                 di.get("firmware_origin_fork", "?"), di.get("hardware_region", "?")),
             "radio   : stack %s.%s  ble_mac %s" % (
                 di.get("radio_stack_major", "?"), di.get("radio_stack_minor", "?"),
                 di.get("radio_ble_mac", "?")),
             "running : " + f.cli("loader info"),
             "sd      : " + " | ".join(x.strip() for x in f.cli("storage info /ext", 15).splitlines()[:3]),
             "", "/ext tree (folder: files/subdirs):"]
        budget = [max_calls]

        def walk(path, d, prefix):
            if budget[0] <= 0:
                return
            budget[0] -= 1
            out = f.cli(f'storage list "{path}"', 40)
            if "error" in out.lower():
                return
            dirs = [l.split("[D]", 1)[1].strip() for l in out.splitlines() if "[D]" in l]
            L.append("%s%s: %d files, %d dirs" % (prefix, path.rsplit("/", 1)[-1] or "/ext",
                                                  out.count("[F]"), len(dirs)))
            if d > 0 and 0 < len(dirs) <= 30:
                for sub in dirs:
                    if budget[0] <= 0:
                        L.append(prefix + "  ...(budget reached)")
                        break
                    walk(path.rstrip("/") + "/" + sub, d - 1, prefix + "  ")
            elif len(dirs) > 30:
                L.append(prefix + "  (%d subdirs - not expanded)" % len(dirs))
        walk("/ext", depth, "")
    return "\n".join(L)


@mcp.tool()
def flipper_find(name: str, path: str = "/ext", max_calls: int = 120) -> str:
    """Recursively search the SD for files/folders whose name contains `name`
    (case-insensitive), starting at `path`. Call-budgeted so it stays fast on big
    trees. Returns matching full paths. Great for 'where is X' before a task."""
    q = name.lower()
    hits = []
    budget = [max_calls]
    with Flipper() as f:
        def walk(p):
            if budget[0] <= 0:
                return
            budget[0] -= 1
            out = f.cli(f'storage list "{p}"', 40)
            if "error" in out.lower():
                return
            subdirs = []
            for l in out.splitlines():
                if "[F]" in l:
                    fn = l.split("[F]", 1)[1].strip().rsplit(" ", 1)[0].strip()
                    if q in fn.lower():
                        hits.append(p.rstrip("/") + "/" + fn)
                elif "[D]" in l:
                    dn = l.split("[D]", 1)[1].strip()
                    if q in dn.lower():
                        hits.append(p.rstrip("/") + "/" + dn + "/")
                    subdirs.append(dn)
            for dn in subdirs:
                if budget[0] <= 0:
                    break
                walk(p.rstrip("/") + "/" + dn)
        walk(path)
    return "\n".join(hits[:100]) or f"no match for {name!r} (searched ~{max_calls - budget[0]} dirs)"
