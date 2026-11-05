#!/usr/bin/env python3
"""Open the stick, say hello, close it. The smallest thing that proves the
whole chain (udev rule, library, firmware) is live.

    pixi run hello
"""

import sys

import ncs1env


def main():
    mvnc = ncs1env.api()
    mvnc.SetGlobalOption(mvnc.GlobalOption.LOG_LEVEL, 1)

    names = mvnc.EnumerateDevices()
    if not names:
        print("no stick found: run `pixi run doctor`")
        return 1
    print("device: %s" % names[0])

    dev = mvnc.Device(names[0])
    try:
        dev.OpenDevice()
    except Exception as e:
        print("open failed: %s" % ncs1env.explain(e.args[0]))
        print("  (uploading firmware is part of open)")
        return 1

    print("opened; firmware is running")

    try:
        opt = dev.GetDeviceOption(mvnc.DeviceOption.TEMPERATURE_DEBUG)
        print("temperature debug mode: %d" % opt)
    except Exception:
        pass

    dev.CloseDevice()
    print("closed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
