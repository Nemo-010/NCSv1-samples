# Attribution

This repo contains no Intel source code. Everything Intel ships is fetched at
runtime, pinned by sha256 in `upstream/pins.sh`.

## Host library and python binding

Fetched from https://github.com/movidius/ncsdk at commit
`c3714ed607d3a4c6612668428765fea82efee166`, unmodified, and compiled here:

* `api/src/mvnc_api.c`, `api/src/usb_boot.c`, `api/src/usb_link_vsc.c`,
  `api/src/*.h`, `api/include/mvnc.h`, `api/include/mvnc_deprecated.h`,
  `api/python/mvnc/mvncapi.py` — Copyright (c) 2017-2018 Intel Corporation,
  Apache License 2.0.

## Device firmware (not distributed here)

`MvNCAPI.mvcmd` is Intel's closed device firmware. It is downloaded by
`scripts/fetch-firmware.sh` from the Internet Archive capture of Intel's
`NCSDK-1.12.01.01.tar.gz`, verified, and left in `build/mvnc/`. It is not part
of this repository and is not covered by any licence here.

## Graph blobs (not distributed here)

`models/inception_v1.graph` comes from the same upstream tree
(`examples/tensorflow/inception_v1/graph`) and is fetched, not committed.

## udev rule

`udev/97-ncs1.rules` is `api/src/97-usbboot.rules` from the same upstream
commit, three lines, copied verbatim as configuration.
