#!/usr/bin/env python3
"""One command from a fresh clone: binding, library, firmware, model, image.

Everything is hash-checked and skipped when already present, so rerunning this
is cheap. It never writes outside this directory.

    pixi run setup
"""

import pathlib
import platform
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from upstream import pins
from tools import util
from tools.util import ROOT, fetch, say, sha256, tar_member

FROM_SOURCE = ROOT / "build" / ".from-source"


def binding():
    for path, want in pins.PYFILES.items():
        fetch("%s/%s" % (pins.NCSDK_RAW, path), ".upstream/" + path, want)


def runtime():
    """Library and firmware, both out of Intel's pinned tarball."""
    fetch(pins.TARBALL_URL, pins.TARBALL_CACHE, pins.TARBALL_SHA256)

    linux_x86 = (sys.platform.startswith("linux") and
                 platform.machine() in ("x86_64", "AMD64"))
    if linux_x86:
        lib = ROOT / pins.LIBRARY_DEST
        # leave a source build alone: `build-local` owns the file once it runs
        if not (lib.is_file() and (FROM_SOURCE.exists() or
                                   sha256(lib) == pins.LIBRARY_SHA256)):
            tar_member(pins.TARBALL_CACHE, pins.LIBRARY_MEMBER,
                       pins.LIBRARY_DEST, pins.LIBRARY_SHA256, "library")
        link = ROOT / "build" / "libmvnc.so"
        if not link.is_symlink():
            link.unlink(missing_ok=True)
            link.symlink_to("libmvnc.so.0")
    else:
        say("no prebuilt library for %s/%s" % (sys.platform, platform.machine()))
        say("  pixi run -e build build-local   builds it from the pinned sources")
    tar_member(pins.TARBALL_CACHE, pins.FIRMWARE_MEMBER, pins.FIRMWARE_DEST,
               pins.FIRMWARE_SHA256, "firmware")


def models():
    before = util.WORK
    fetch(pins.GRAPH_URL, pins.GRAPH_DEST, pins.GRAPH_SHA256)
    fetch(pins.LABELS_URL, pins.LABELS_DEST, pins.LABELS_SHA256)
    fetch(pins.IMAGE_URL, pins.IMAGE_DEST, pins.IMAGE_SHA256)
    if util.WORK != before:
        say("model: %s (%d bytes)" %
            (pins.GRAPH_DEST, (ROOT / pins.GRAPH_DEST).stat().st_size))


def main():
    binding()
    runtime()
    models()
    if util.WORK:
        say("ready: pixi run hello")
    return 0


if __name__ == "__main__":
    sys.exit(main())
