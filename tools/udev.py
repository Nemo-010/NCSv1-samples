#!/usr/bin/env python3
"""The one thing in this repo that wants root, and it is three lines of rules.

This prints the install commands for the host it finds; it never runs them.

    pixi run udev
"""

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
RULE_SRC = ROOT / "udev" / "97-ncs1.rules"


def main():
    if sys.platform != "linux":
        print("udev is a Linux thing; on %s the stick needs a different answer"
              % sys.platform)
        print("(Intel's driver story stopped before anything else existed)")
        return 1
    rule = pathlib.Path("/etc/udev/rules.d/97-ncs1.rules")
    if rule.is_file() and rule.read_text(errors="replace") == RULE_SRC.read_text():
        print("installed: %s" % rule)
        return 0
    print("""not installed. run, once:

  sudo install -m 0644 %s %s
  sudo udevadm control --reload-rules && sudo udevadm trigger

then replug the stick. the rules only set MODE 0666 on 03e7:2150 and
03e7:f63b, so opening the device does not need root. nothing else in this
project installs outside its own directory.""" % (RULE_SRC, rule))
    return 1


if __name__ == "__main__":
    sys.exit(main())
