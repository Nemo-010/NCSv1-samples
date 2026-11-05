#!/usr/bin/env python3
"""Compile libmvnc.so.0 from the pinned upstream sources, replacing Intel's
prebuilt binary. Three C files and libusb; the compiler comes from the pixi
environment, so nothing needs installing on the host.

    pixi run -e build build-local
"""

import os
import pathlib
import platform
import shutil
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from upstream import pins
from tools.util import ROOT, die, fetch, say

SOURCES = ("api/src/usb_boot.c", "api/src/usb_link_vsc.c", "api/src/mvnc_api.c")


def sources():
    for path, want in pins.SRCFILES.items():
        fetch("%s/%s" % (pins.NCSDK_RAW, path), ".upstream/" + path, want)
    say("sources: %d files from %s@%s" %
        (len(pins.SRCFILES), pins.NCSDK_REPO, pins.NCSDK_COMMIT[:12]))


def compiler():
    cc = os.environ.get("CC") or shutil.which("cc") or shutil.which("gcc")
    if not cc:
        die("no C compiler in this environment; run this through "
            "`pixi run -e build build-local`")
    return cc


def main():
    prefix = os.environ.get("CONDA_PREFIX")
    if not prefix:
        die("run this through pixi, so libusb and the headers come from the env")
    sources()
    cc = compiler()

    src = ROOT / ".upstream" / "api" / "src"
    out = ROOT / pins.LIBRARY_DEST
    out.parent.mkdir(parents=True, exist_ok=True)

    cmd = [cc, "-O2", "-Wall", "-fPIC", "-shared", "-pthread",
           "-I%s" % src,
           "-I%s" % (ROOT / ".upstream" / "api" / "include"),
           "-I%s" % (pathlib.Path(prefix) / "include" / "libusb-1.0")]
    cmd += [str(src / s.split("/")[-1]) for s in SOURCES]
    cmd += ["-lusb-1.0", "-lpthread", "-ldl",
            "-Wl,-rpath,$ORIGIN",
            "-Wl,-rpath,%s" % (pathlib.Path(prefix) / "lib"),
            "-o", str(out)]

    say("build %s from source on %s/%s" %
        (pins.LIBRARY_DEST, sys.platform, platform.machine()))
    r = subprocess.run(cmd)
    if r.returncode != 0:
        die("compiler failed (%d)" % r.returncode)

    link = ROOT / "build" / "libmvnc.so"
    link.unlink(missing_ok=True)
    link.symlink_to("libmvnc.so.0")
    # tells setup.py not to put Intel's binary back
    (ROOT / "build" / ".from-source").write_text("%s/%s\n" %
                                                (sys.platform, platform.machine()))
    say("done: %d bytes (pixi run setup will leave this in place)" %
        out.stat().st_size)
    return 0


if __name__ == "__main__":
    sys.exit(main())
