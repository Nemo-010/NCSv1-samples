#!/usr/bin/env python3
"""Say why the stick is not working, in one screen.

Nothing here needs root and nothing here changes anything: it reads the built
library, the firmware blob, the udev rules, the USB tree and finally asks the
API what it can see.

    pixi run doctor
"""

import hashlib
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from upstream import pins

ROOT = pathlib.Path(__file__).resolve().parent.parent
NCS_IDS = {("03e7", "2150"): "before firmware upload",
           ("03e7", "f63b"): "after firmware upload"}


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class Report:
    def __init__(self):
        self.rows = []
        self.failed = False

    def add(self, name, state, detail, fix=""):
        if state == "fail":
            self.failed = True
        self.rows.append((name, state, detail, fix))

    def show(self):
        width = max(len(r[0]) for r in self.rows)
        for name, state, detail, fix in self.rows:
            print("  %-*s  %-4s  %s" % (width, name, state, detail))
            if fix:
                print("  %-*s        %s" % (width, "", fix))
        print()
        print("  nothing is broken" if not self.failed
              else "  fix the rows marked fail, then rerun")


def check_env(r):
    import numpy
    import PIL
    r.add("python", "ok", "%s  (numpy %s, pillow %s)" %
          (sys.version.split()[0], numpy.__version__, PIL.__version__))


def check_library(r):
    lib = ROOT / pins.LIBRARY_DEST
    if not lib.is_file():
        r.add("libmvnc", "fail", "%s missing" % pins.LIBRARY_DEST, "pixi run setup")
        return
    got = sha256(lib)
    if got == pins.LIBRARY_SHA256:
        kind = "Intel prebuilt"
    elif (ROOT / "build" / ".from-source").is_file():
        kind = "built from source"
    else:
        kind = "not the pinned blob"
    r.add("libmvnc", "ok", "%s  %d B  %s" %
          (pins.LIBRARY_DEST, lib.stat().st_size, kind))


def check_firmware(r):
    fw = ROOT / pins.FIRMWARE_DEST
    if not fw.is_file():
        r.add("firmware", "fail", "%s missing" % pins.FIRMWARE_DEST, "pixi run setup")
        return
    got = sha256(fw)
    if got != pins.FIRMWARE_SHA256:
        r.add("firmware", "fail", "%s is not the pinned blob" % pins.FIRMWARE_DEST,
              "pixi run setup")
        return
    r.add("firmware", "ok", "%d B  sha256 %s" % (fw.stat().st_size, got[:16]))


def check_udev(r):
    rules = pathlib.Path("/etc/udev/rules.d")
    if not rules.is_dir():
        r.add("udev rule", "warn", "no /etc/udev/rules.d here; nothing to check")
        return
    for f in sorted(rules.glob("*.rules")):
        try:
            text = f.read_text(errors="replace")
        except OSError:
            continue
        if "03e7" in text and ("2150" in text or "f63b" in text):
            r.add("udev rule", "ok", str(f))
            return
    r.add("udev rule", "warn", "no rule for 03e7:2150 or 03e7:f63b",
          "pixi run udev")


def check_usb(r):
    found = []
    for dev in pathlib.Path("/sys/bus/usb/devices").glob("*"):
        try:
            vid = (dev / "idVendor").read_text().strip()
            pid = (dev / "idProduct").read_text().strip()
        except OSError:
            continue
        if (vid, pid) in NCS_IDS:
            found.append((dev, vid, pid))
    if not found:
        r.add("usb", "warn", "no 03e7:2150 or 03e7:f63b on the bus",
              "plug the stick in, then rerun")
        return
    for dev, vid, pid in found:
        try:
            bus = int((dev / "busnum").read_text())
            num = int((dev / "devnum").read_text())
        except OSError as e:
            r.add("usb", "warn", "%s:%s, cannot resolve its node (%s)" % (vid, pid, e))
            continue
        node = pathlib.Path("/dev/bus/usb/%03d/%03d" % (bus, num))
        if not node.exists():
            r.add("usb", "warn", "%s:%s but %s is absent" % (vid, pid, node))
            continue
        st = node.stat()
        writable = os.access(node, os.W_OK)
        r.add("usb", "ok" if writable else "warn",
              "%s:%s  %s  %s  mode %s" %
              (vid, pid, NCS_IDS[(vid, pid)], node, oct(st.st_mode & 0o777)[2:]),
              "" if writable else
              "uid %d cannot write it; that is what the udev rule is for" % os.geteuid())


def check_api(r):
    try:
        import ncs1env
        mvnc = ncs1env.api()
    except Exception as e:
        r.add("mvnc api", "fail", "import failed: %s" % e, "pixi run setup")
        return
    try:
        names = mvnc.EnumerateDevices()
    except Exception as e:
        r.add("mvnc api", "fail", "EnumerateDevices failed: %s" % e)
        return
    if names:
        r.add("mvnc api", "ok", "EnumerateDevices() -> %s" % ", ".join(names))
    else:
        r.add("mvnc api", "warn", "EnumerateDevices() -> []", "pixi run hello")


def main():
    print("\nNCSv1 doctor\n")
    r = Report()
    check_env(r)
    check_library(r)
    check_firmware(r)
    check_udev(r)
    check_usb(r)
    check_api(r)
    r.show()
    return 1 if r.failed else 0


if __name__ == "__main__":
    sys.exit(main())
