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
| `NCSv1-hello/`, `NCSv1-infer/` | samples. |
| `.upstream/`, `build/`, `models/` | generated, gitignored. |

Sources are fetched at a pinned commit and hash-checked, never vendored and
never edited, so a changed upstream cannot change your build quietly. Moving to
another upstream commit means changing `NCSDK_COMMIT` and the hashes together,
in one file, on purpose.

Two environments, because the compiler is the heaviest thing here and running a
sample does not need it: `default` is python/numpy/pillow/libusb, `build` adds
`c-compiler` and exists for `build-local`.

## Samples

Scheme: `NCSv1-<what it does>/`, one directory each, with a pixi task that
points at its `run.py`. A sample does one thing, takes its inputs as flags, and
reports device trouble through `ncs1env.explain()` rather than a traceback.

* `NCSv1-hello` — enumerate, open, close. Proves udev, library and firmware.
* `NCSv1-infer` — centre-crop, resize, classify, top-k, optional `--repeat`
  timing. Pillow and numpy do the image; the graph blob goes to the device
  untouched.

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

## Platforms

The workflow — fetching, hashing, extracting, building, diagnosing — is Python
standard library, so it behaves the same anywhere pixi does.

The runtime is narrower, because the hardware is: Intel's prebuilt library is a
linux x86_64 ELF, and the sources are POSIX C over libusb. On other platforms
put your own platform in `pixi.toml`, then `pixi run -e build build-local` and
the compiler comes from the environment. There is no Windows path for this
stick that this repo can offer.

## If it does not work

`pixi run doctor` first. The usual three:

* `DEVICE_NOT_FOUND` — the udev rule is not loaded, or the node is not
  writable by you. Doctor shows the node's mode and owner.
* `MVCMD_NOT_FOUND` — the firmware is not next to the library. `pixi run setup`.
* `UNSUPPORTED_GRAPH_FILE` / `MYRIAD_ERROR` — the blob was not built for this
  SDK, or was built for MA2485 (NCS2) rather than MA2450.

`GONE` means the stick dropped off the bus: replug it. `ncs1env.py` has the full
status list.
