#!/usr/bin/env python3
"""Classify one image on the stick: the everyday use of the thing.

    pixi run infer -- --image foo.jpg
    pixi run infer -- --image foo.jpg --graph models/other.graph --size 224 \
        --labels models/categories.txt --repeat 50

Only pillow and numpy touch the image; the graph blob is passed through to the
device untouched. Defaults match the pinned inception_v1 example: 224x224 RGB,
mean 128, std 1/128.
"""

import argparse
import struct
import sys
import time

import numpy
from PIL import Image

import ncs1env

HEADER_LENGTH = 264
STAGE_LENGTH = 227
VERSION_OFFSET = 36
N_STAGES_OFFSET = 240
GRAPH_VERSION = 2


def inspect_graph(blob):
    """The same header check mvncAllocateGraph makes, without a device."""
    if len(blob) < HEADER_LENGTH + STAGE_LENGTH:
        raise SystemExit("graph too short: %d bytes" % len(blob))
    version = blob[VERSION_OFFSET]
    if version != GRAPH_VERSION:
        raise SystemExit("graph format v%d, this SDK loads v%d" %
                         (version, GRAPH_VERSION))
    stages = blob[N_STAGES_OFFSET] | (blob[N_STAGES_OFFSET + 1] << 8)
    return stages


def load_image(path, size, mean, std):
    img = Image.open(path).convert("RGB")
    w, h = img.size
    side = min(w, h)
    img = img.crop(((w - side) // 2, (h - side) // 2,
                    (w - side) // 2 + side, (h - side) // 2 + side))
    img = img.resize((size, size), Image.BICUBIC)
    arr = numpy.asarray(img, dtype=numpy.float32)
    return (arr - mean) * std


def load_labels(path):
    labels = []
    with open(path) as f:
        for line in f:
            line = line.rstrip("\n")
            if line and line != "classes":
                labels.append(line)
    return labels


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", required=True, help="image to classify")
    ap.add_argument("--graph", default="models/inception_v1.graph")
    ap.add_argument("--labels", default="models/categories.txt")
    ap.add_argument("--size", type=int, default=224)
    ap.add_argument("--mean", type=float, default=128.0)
    ap.add_argument("--std", type=float, default=1.0 / 128.0)
    ap.add_argument("--repeat", type=int, default=1,
                    help="run the tensor more than once and report timing")
    ap.add_argument("--topk", type=int, default=5)
    args = ap.parse_args()

    with open(args.graph, "rb") as f:
        blob = f.read()
    stages = inspect_graph(blob)
    print("graph: %s  v%d  %d stages  %d B" %
          (args.graph, blob[VERSION_OFFSET], stages, len(blob)))

    labels = load_labels(args.labels)
    x = load_image(args.image, args.size, args.mean, args.std)
    print("image: %s -> %dx%d fp16, %d labels" % (args.image, args.size, args.size,
                                                 len(labels)))

    mvnc = ncs1env.api()
    mvnc.SetGlobalOption(mvnc.GlobalOption.LOG_LEVEL, 1)
    names = mvnc.EnumerateDevices()
    if not names:
        print("no stick found: run `pixi run doctor`")
        return 1

    dev = mvnc.Device(names[0])
    try:
        dev.OpenDevice()
    except Exception as e:
        print("open failed: %s" % ncs1env.explain(e.args[0]))
        return 1

    try:
        graph = dev.AllocateGraph(blob)
    except Exception as e:
        print("allocation failed: %s" % ncs1env.explain(e.args[0]))
        dev.CloseDevice()
        return 1

    fp16 = ncs1env.tensor(x)
    best = None
    t0 = time.perf_counter()
    for i in range(max(1, args.repeat)):
        graph.LoadTensor(fp16, "image")
        out, _ = graph.GetResult()
        if out is None:
            print("no result: %s" % ncs1env.explain(mvnc.Status.NO_DATA))
            break
        if i == args.repeat - 1:
            best = numpy.array(out, dtype=numpy.float32)
    dt = time.perf_counter() - t0

    graph.DeallocateGraph()
    dev.CloseDevice()

    if best is None:
        return 1
    if args.repeat > 1:
        print("%d inferences in %.3f s: %.2f ms each, %.1f/s" %
              (args.repeat, dt, 1000 * dt / args.repeat, args.repeat / dt))

    order = best.argsort()[::-1][:args.topk]
    print()
    for i in order:
        label = labels[i] if i < len(labels) else "class %d" % i
        print("  %6.4f  %s" % (best[i], label))
    return 0


if __name__ == "__main__":
    sys.exit(main())
