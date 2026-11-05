"""Everything that stands between this repo and Intel's python binding.

mvncapi.py is used unmodified. One method of it, Graph.LoadTensor, calls
ndarray.tostring(), which numpy 2 removed, so the upstream file would raise on
any modern numpy. Instead of pinning an old numpy or editing Intel's file, the
samples hand it an ndarray subclass that still answers to tostring().
"""

import numpy
from mvnc import mvncapi


class _Tensor(numpy.ndarray):
    def tostring(self):
        return self.tobytes()


def api():
    return mvncapi


def tensor(array):
    """`array` as fp16, in a form upstream's LoadTensor can serialise."""
    return numpy.ascontiguousarray(array, dtype=numpy.float16).view(_Tensor)


# mvncStatus -> what it means and what to do about it. The device never says
# which of its two ends gave up, so these are the usual causes, in order.
_STATUS = {
    "BUSY": "the stick already has a graph loaded; close it, or replug if a "
            "process died holding it",
    "ERROR": "USB traffic failed; try another port, and no hub",
    "OUT_OF_MEMORY": "out of host memory while setting up the transfer",
    "DEVICE_NOT_FOUND": "no stick at that index; check it is plugged in and "
                        "the udev rule is loaded (pixi run doctor)",
    "INVALID_PARAMETERS": "the call was given something it cannot accept",
    "TIMEOUT": "the stick stopped answering mid-transfer",
    "MVCMD_NOT_FOUND": "firmware missing next to libmvnc; pixi run setup",
    "NO_DATA": "no result yet; LoadTensor first",
    "GONE": "the stick fell off the bus; replug it",
    "UNSUPPORTED_GRAPH_FILE": "not a v2 stage-table graph; this SDK only loads "
                              "blobs compiled for MA2450",
    "MYRIAD_ERROR": "the device rejected the graph; read GraphOption.DEBUG_INFO "
                    "for its own message",
}


def explain(status):
    """One line for a non-OK mvncStatus."""
    name = getattr(status, "name", str(status))
    return "%s: %s" % (name, _STATUS.get(name, "unknown status"))
