# NCSv1-samples

The small way to run things on an Intel Movidius Neural Compute Stick (NCS1,
Myriad 2 / MA2450): a pixi workspace, a host library with no forked anything,
one udev rule, and samples you can run straight away.

NCSDK's own `install.sh` builds a patched OpenCV into `/usr/local`, installs a
forked Caffe and a TensorFlow 1.12 for the compiler, and pins the rest of a
2018 Python world around it. None of that is the runtime. The part that talks
to the hardware is a small C library, `libusb` and a firmware blob. That is
what this repo gives you, and it never writes outside its own directory.

## Three commands from a clone

```sh
pixi install                 # python, numpy, pillow, libusb — from conda-forge
pixi run demo                # fetches what it needs, then classifies an image
pixi run doctor              # says which link is broken, if any
```

...plus one, once, with root, for the stick itself:

```sh
pixi run udev                # prints the exact sudo lines; it does not run them
```

`pixi run demo` is the "fire it up and see" command: it runs `setup` first if
anything is missing, then loads the pinned graph and classifies a bundled
photo. Without a stick plugged in it stops at `no stick found` and tells you to
run `doctor`, which is the honest end of the road on a machine with no hardware
attached.

The rest of the surface:

```sh
pixi run hello                                  # enumerate, open, close
pixi run infer -- --image picture.jpg           # classify your own image
pixi run infer -- --image picture.jpg --repeat 50 --graph models/mine.graph
pixi run -e camera camera                       # live loop, window + labels
pixi run -e camera camera --preview http        # same frames as a local MJPEG page
pixi run -e camera camera --source clip.mp4 --dry-run
pixi run -e build build-local                   # library from source, not Intel's binary
```

## The only thing installed outside this repo

`/etc/udev/rules.d/97-ncs1.rules`, three lines setting `MODE 0666` on
`03e7:2150` and `03e7:f63b` so opening the stick does not need root. Nothing
else goes to `/usr`, nothing is registered with `ldconfig`, no Python package
is installed into the environment's site-packages: the binding is imported
from `.upstream/` and the library is loaded from `./build`.

## How it is laid out

| path | what it is |
| --- | --- |
| `pixi.toml` | environments and tasks. The whole project interface. |
| `upstream/pins.py` | every third-party artefact and its sha256, in one importable file. |
| `tools/` | Python, standard library only: `util` (verified download, tar member, sha256), `setup`, `build_local`, `doctor`, `udev`. |
| `ncs1env.py` | the only shim: a numpy-2-compatible tensor for Intel's unchanged binding, plus status explanations. |
| `NCSv1-*/` | samples. |
| `.upstream/`, `build/`, `models/` | generated, gitignored. |

Sources are fetched at a pinned commit and hash-checked, never vendored and
never edited, so a changed upstream cannot change your build quietly. Moving to
another upstream commit means changing `NCSDK_COMMIT` and the hashes together,
in one file, on purpose.

Three environments, so a sample only pays for what it uses: `default` is
python/numpy/pillow/libusb, `build` adds `c-compiler` for `build-local`,
`camera` adds `ffmpeg` for the live loop.

## Samples

Scheme: `NCSv1-<what it does>/`, one directory each, with a pixi task that
points at its `run.py`. A sample does one thing, takes its inputs as flags, and
reports device trouble through `ncs1env.explain()` rather than a traceback.

* `NCSv1-hello` — enumerate, open, close. Proves udev, library and firmware.
* `NCSv1-infer` — centre-crop, resize, classify, top-k, optional `--repeat`
  timing. Pillow and numpy do the image; the graph blob goes to the device
  untouched.
* `NCSv1-camera` — the live loop: frames from ffmpeg, one graph, a preview with
  the top-k labels drawn on it, per-frame inference rate on the status line,
  Ctrl-C to stop. `--dry-run` reads frames and checks the pipeline without a
  stick, which is also how the sample is tested.

The camera sample uses ffmpeg for capture instead of OpenCV: one conda-forge
package, it owns the V4L2 ioctls and the colour conversion, and it is not a
fork of anything, so `cv2` is still not installed anywhere. Point `--source` at
a device, a video file, or a `lavfi:` pattern.

The preview has three modes, because "show me the frames" has three answers:

| `--preview` | what you get |
| --- | --- |
| `window` (default) | a tkinter window, frames plus the labels drawn on them. Falls back with a message when there is no display. |
| `http` | the same frames as `multipart/x-mixed-replace` on `127.0.0.1:8099`, so any browser can watch it (loopback only) and a headless box still has a preview |
| `off` | nothing; the status line only |

`--preview-size` (384 by default) is display only: the stick always gets
`--size` (224). Both the window and the stream show exactly the crop the model
sees, upscaled, rather than the raw camera frame with the crop hidden.

## What is not ported, and why

Upstream has ten examples. Three are here, in their useful form, and the rest
fall into two honest buckets:

* **Needs a graph nobody can build any more.** `caffe/AlexNet`,
  `caffe/GoogLeNet`, `caffe/SqueezeNet` and `tensorflow/inception_v3` are all
  "load this blob and classify". The code is the same shape as `NCSv1-infer`,
  which already takes `--graph`, so the missing piece is the blob: upstream
  ships one for inception_v1 (pinned here) and one for inception_v3 — a valid
  v2 blob, 54 MB, 114 stages, sha256 `8c55ade2…0705c` — which is not pinned
  because nobody wants 54 MB in a first run. The Caffe ones ship
  no blob at all, and making one means Intel's compiler on the forked
  TensorFlow. `NCSv1-infer --graph yours.graph` is the port; the graph is the
  part this repo cannot supply.
* **Needs hardware or a stack that is not this one.** `apps/multistick_cpp`
  wants two sticks and is the same API calls in a loop over device names.
  Current `ncappzoo` samples (`simple_classifier_py_camera`, `birds`,
  `gender_age`, `classifier_gui`, the realsense ones) have moved to OpenVINO's
  MYRIAD plugin with IR files, which is NCS2 territory: they are not NCSDK
  samples any more and nothing in them loads on MA2450. `birds` imports
  `openvino.inference_engine` and wants `googlenet-v1.xml`; `classifier_gui`
  wants three IRs; `simple_classifier_py_camera` wants OpenVINO's `setupvars.sh`
  to be sourced before it even starts.

So the camera one did not get ported from a file, it got rewritten around the
one graph this SDK generation can still load. If you want a specific ncappzoo
app, say which and check whether an NCS1 `.graph` for its network exists
anywhere; if it does, it is a ten-line sample here.

## What is still Intel's

Two things, and they are why this is not a from-scratch stack:

* **Firmware.** `MvNCAPI.mvcmd` is a closed blob that is uploaded before the
  stick answers at all. Intel's download mirror has answered 403 for years;
  `upstream/pins.py` points at the Internet Archive capture of the exact
  tarball NCSDK's `get_mvcmd.sh` asked for, and checks both the tarball and the
  extracted file. It lands at `build/mvnc/MvNCAPI.mvcmd`, which is where the
  library looks: next to itself, in a directory called `mvnc/`.
* **Graph compiler.** `.graph` blobs are produced by Intel's `mvNCCompile`,
  which runs on the forked TensorFlow. There is no second implementation. So
  blobs are pinned opaque inputs here (`models/`), and carrying your own is one
  flag away; compiling new ones still means the 2018 stack, which is out of
  scope on purpose. Anything that is already a v2 stage-table blob built for
  MA2450 will load.

The host library itself is either Intel's prebuilt x86_64 binary from the same
tarball (the default, 32 KB) or a build from the pinned sources
(`pixi run -e build build-local`). Both are hash-checked; `doctor` tells you
which one you are running.

## Platform: linux x86_64 only

`pixi.toml` declares `platforms = ["linux-64"]` and the lockfile contains no
other target. That is the whole support statement: this is not a portable
project that happens to run here, it is a project for one platform.

The reason is the hardware, not the tooling. Intel's `libmvnc.so.0` is a linux
x86_64 ELF object, the fallback build is POSIX C over libusb, and the stick has
no Windows driver path at all. The Python in `tools/` would run anywhere; the
runtime it sets up would not.

## If it does not work

`pixi run doctor` first. The usual three:

* `DEVICE_NOT_FOUND` — the udev rule is not loaded, or the node is not
  writable by you. Doctor shows the node's mode and owner.
* `MVCMD_NOT_FOUND` — the firmware is not next to the library. `pixi run setup`.
* `UNSUPPORTED_GRAPH_FILE` / `MYRIAD_ERROR` — the blob was not built for this
  SDK, or was built for MA2485 (NCS2) rather than MA2450.

`GONE` means the stick dropped off the bus: replug it. `ncs1env.py` has the full
status list.
