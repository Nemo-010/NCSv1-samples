"""Every third-party artefact this repo consumes, pinned once, here.

Nothing is forked: each file is fetched byte-for-byte from the upstream tree
and checked against its sha256, so a changed upstream cannot change the build
silently. Moving to another upstream commit means changing NCSDK_COMMIT and the
hashes together, on purpose, in one file.
"""

# --- Intel's NCSDK tree (Apache-2.0): host library sources and binding ------
NCSDK_REPO = "https://github.com/movidius/ncsdk"
NCSDK_COMMIT = "c3714ed607d3a4c6612668428765fea82efee166"
NCSDK_RAW = "https://raw.githubusercontent.com/movidius/ncsdk/%s" % NCSDK_COMMIT

# python binding: needed always
PYFILES = {
    "api/python/mvnc/__init__.py":
        "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "api/python/mvnc/mvncapi.py":
        "d51adf03673e3aae71f05adb45adb3bde18334a3156246f418b71e78372cb8f2",
}

# C sources: needed only by `pixi run build-local`
SRCFILES = {
    "api/src/mvnc_api.c":
        "a6837ba51a979131af892a423c0c405f742a48c01895c1ae74ba917fa6f15ffd",
    "api/src/usb_boot.c":
        "eda32593879c0b80fb9d03827cb05f94093f4c5a921578a19b001b88edeaf2a9",
    "api/src/usb_link_vsc.c":
        "981aec0004950220ccffb8589bcf1c1b8fa9b034a878210e5cde248aea3a71c9",
    "api/src/USBLinkDefines.h":
        "adee3728b68bf613bf00b0baa9df9a863356820200d1c344ac2c912e506025e8",
    "api/src/common.h":
        "8a2d870ad7f73f1dae2133cd1c3732274b0e3f1eab45b8cc9a75f8063b316831",
    "api/src/usb_boot.h":
        "c5f3a76f81c51574898167d4fbf3a09542ffa583ce80f0c8c13ab6d74001aca7",
    "api/src/usb_link.h":
        "085b5ce49ed82386edc6695faed09bece27806ef9532ee9dedfae120bc1fa715",
    "api/include/mvnc.h":
        "2b97149c04b407279ad83bf440a26b1736d472e015c73536cb9bd0c8b777af89",
    "api/include/mvnc_deprecated.h":
        "cae3d2cfa52b0ce031f30203fc96a5f035fa0e6fce10f1fe52e29a6e2ba837ad",
}

# --- the runtime tarball: firmware blob + Intel's prebuilt library ----------
# Intel's downloadmirror.intel.com/28192 went 403 years ago; this is the
# Internet Archive capture of the exact tarball NCSDK's get_mvcmd.sh asked for.
# 966 KB, and it is the only download this project really needs.
TARBALL_URL = ("https://web.archive.org/web/20191119142208id_/"
               "https://downloadmirror.intel.com/28192/eng/NCSDK-1.12.01.01.tar.gz")
TARBALL_SHA256 = "df5261ab79697f3c564279010aebbc8fd171f57290a84f636201aee82368a3b2"
TARBALL_CACHE = ".upstream/NCSDK-1.12.01.01.tar.gz"

# The firmware is uploaded before the stick answers anything at all. It is the
# one closed artefact here and the only thing that cannot be built.
FIRMWARE_MEMBER = "NCSDK-1.12.01.01/ncsdk-x86_64/fw/MvNCAPI.mvcmd"
FIRMWARE_SHA256 = "bd0ef7bed794379d4c77f4d2434dfa0da905acdd2abbf8df64a23d69cc5a49c0"
FIRMWARE_DEST = "build/mvnc/MvNCAPI.mvcmd"

# Intel's own x86_64 build of the host library, from the same tarball. Used
# unless you run `pixi run build-local`. Only meaningful on linux x86_64: it is
# an ELF object, so anywhere else you build from SRCFILES instead.
LIBRARY_MEMBER = "NCSDK-1.12.01.01/ncsdk-x86_64/api/c/libmvnc.so.0"
LIBRARY_SHA256 = "b3c48818863eef464b9c334751fbc0c41801501f738735b95d2f35c844ae34dd"
LIBRARY_DEST = "build/libmvnc.so.0"
LIBRARY_PLATFORMS = ("linux", "x86_64")

# --- one graph blob and its labels, so a sample has something to load -------
# Compiled by Intel for this SDK: graph format v2, stage table, 73 stages.
GRAPH_URL = "%s/examples/tensorflow/inception_v1/graph" % NCSDK_RAW
GRAPH_SHA256 = "1aa9faa7ba6a02cee5e1a32b5faf06f5ce51b881a6f5c8a227bde1d4babf45a3"
GRAPH_DEST = "models/inception_v1.graph"
LABELS_URL = "%s/examples/tensorflow/inception_v1/categories.txt" % NCSDK_RAW
LABELS_SHA256 = "5442099ff5ee4f9a943ed8518e2cc0e4294415bfb8d6e545c17bc5bd0c93b5c7"
LABELS_DEST = "models/categories.txt"

# --- and one image, so `pixi run demo` runs straight after setup ------------
IMAGE_URL = "%s/examples/data/images/nps_electric_guitar.png" % NCSDK_RAW
IMAGE_SHA256 = "0e88faefb8a53ce97007a7ad91fc23abd854731c7780c9c96497eec1fb24ab8a"
IMAGE_DEST = "models/guitar.png"
