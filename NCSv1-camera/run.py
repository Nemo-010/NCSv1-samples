#!/usr/bin/env python3
"""Classify live frames from a camera: the thing you would actually leave running.

    pixi run -e camera camera                        # /dev/video0
    pixi run -e camera camera --source /dev/video2
    pixi run -e camera camera --frames 200 --topk 3
    pixi run -e camera camera --source clip.mp4 --dry-run   # no stick needed

Frames come from ffmpeg rather than OpenCV: it is one conda-forge package, it
does the V4L2 ioctls and the colour conversion, and it is not a fork of
anything. When this sample is done, cv2 is still not installed.

Upstream's camera sample cannot be carried over as-is: current ncappzoo drives
OpenVINO's MYRIAD plugin with IR files, which is NCS2 territory, and it ships no
NCS1 .graph blobs at all. This is the same idea against a graph that loads.
"""

import argparse
import os
import shutil
import subprocess
import sys
import time

import numpy

import ncs1env


class Frames:
    """ffmpeg stdout as size x size RGB frames, centre-cropped.

    A class rather than a generator so the caller can read ffmpeg's complaint
    when a camera turns out not to be there.
    """

    def __init__(self, source, size):
        self.source = source
        self.size = size
        self.nbytes = size * size * 3
        self.proc = None
        self.error = ""
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            raise SystemExit("no ffmpeg in this environment: pixi run -e camera camera")
        vf = ("scale=%d:%d:force_original_aspect_ratio=increase,crop=%d:%d"
              % (size, size, size, size))
        cmd = [ffmpeg, "-nostdin", "-loglevel", "error"] + self._input()
        cmd += ["-vf", vf, "-pix_fmt", "rgb24", "-f", "rawvideo", "-"]
        self.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE, bufsize=self.nbytes * 4)

    def _input(self):
        src = self.source
        if src.startswith("lavfi:"):
            return ["-f", "lavfi", "-i", src[len("lavfi:"):]]
        if os.path.isfile(src):
            return ["-re", "-i", src]
        return ["-f", "v4l2", "-i", src]

    def __iter__(self):
        try:
            while True:
                buf = self.proc.stdout.read(self.nbytes)
                if not buf or len(buf) < self.nbytes:
                    return
                yield numpy.frombuffer(buf, dtype=numpy.uint8).reshape(
                    self.size, self.size, 3)
        except KeyboardInterrupt:
            return

    def close(self):
        if not self.proc:
            return
        self.proc.stdout.close()
        self.proc.terminate()
        try:
            self.error = (self.proc.stderr.read() or b"").decode("utf-8", "replace").strip()
        except Exception:
            pass
        self.proc.wait()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default="/dev/video0",
                    help="camera device, video file, or lavfi:pattern")
    ap.add_argument("--graph", default="models/inception_v1.graph")
    ap.add_argument("--labels", default="models/categories.txt")
    ap.add_argument("--size", type=int, default=224)
    ap.add_argument("--mean", type=float, default=128.0)
    ap.add_argument("--std", type=float, default=1.0 / 128.0)
    ap.add_argument("--topk", type=int, default=1)
    ap.add_argument("--frames", type=int, default=0, help="0 runs until Ctrl-C")
    ap.add_argument("--dry-run", action="store_true",
                    help="read frames and stop before touching the stick")
    args = ap.parse_args()

    with open(args.labels) as f:
        labels = [l.rstrip("\n") for l in f if l.strip() and l.strip() != "classes"]

    mvnc = ncs1env.api()
    mvnc.SetGlobalOption(mvnc.GlobalOption.LOG_LEVEL, 1)

    device = graph = None
    if not args.dry_run:
        with open(args.graph, "rb") as f:
            blob = f.read()
        names = mvnc.EnumerateDevices()
        if not names:
            print("no stick found: run `pixi run doctor`")
            return 1
        device = mvnc.Device(names[0])
        try:
            device.OpenDevice()
        except Exception as e:
            print("open failed: %s" % ncs1env.explain(e.args[0]))
            return 1
        try:
            graph = device.AllocateGraph(blob)
        except Exception as e:
            print("allocation failed: %s" % ncs1env.explain(e.args[0]))
            device.CloseDevice()
            return 1

    print("camera: %s -> %dx%d rgb24 via ffmpeg" % (args.source, args.size, args.size))
    frames = Frames(args.source, args.size)
    start = time.perf_counter()
    n = 0
    infer_ms = 0.0
    try:
        for frame in frames:
            n += 1
            x = (frame.astype(numpy.float32) - args.mean) * args.std
            if args.dry_run:
                if n == 1:
                    print("frame 0: %s -> %d bytes fp16, mean %.2f, range %.2f..%.2f"
                          % (frame.shape, x.size * 2, float(x.mean()),
                             float(x.min()), float(x.max())))
                if args.frames and n >= args.frames:
                    break
                continue

            t0 = time.perf_counter()
            graph.LoadTensor(ncs1env.tensor(x), "frame")
            out, _ = graph.GetResult()
            infer_ms += (time.perf_counter() - t0) * 1000.0
            if out is None:
                continue
            order = numpy.array(out, dtype=numpy.float32).argsort()[::-1][:args.topk]
            text = "  ".join("%s %.2f" %
                             (labels[i] if i < len(labels) else i, float(out[i]))
                             for i in order)
            sys.stdout.write("\rframe %-5d %6.1f ms %5.1f/s  %s\x1b[K" %
                             (n, infer_ms / n, n / (time.perf_counter() - start), text))
            sys.stdout.flush()
            if args.frames and n >= args.frames:
                break
    except KeyboardInterrupt:
        pass
    finally:
        elapsed = time.perf_counter() - start
        frames.close()
        if not args.dry_run:
            if graph:
                graph.DeallocateGraph()
            if device:
                device.CloseDevice()

    print()
    if n == 0:
        print("no frames from %s" % args.source)
        if frames.error:
            print("ffmpeg: %s" % frames.error)
        elif not args.dry_run:
            print("(the camera is not there, or it is not readable by you)")
        return 1
    if args.dry_run:
        print("dry run: %d frames in %.2fs (%.1f/s), no device touched" %
              (n, elapsed, n / elapsed))
    else:
        print("%d frames in %.2fs: %.1f ms per inference, %.1f/s" %
              (n, elapsed, infer_ms / n, n / elapsed))
    return 0


if __name__ == "__main__":
    sys.exit(main())
