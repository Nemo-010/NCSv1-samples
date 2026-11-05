#!/usr/bin/env python3
"""Classify live frames from a camera, with a preview of what the stick sees.

    pixi run -e camera camera                        # /dev/video0, window + overlay
    pixi run -e camera camera --preview http         # local MJPEG page instead
    pixi run -e camera camera --source /dev/video2 --preview off
    pixi run -e camera camera --source clip.mp4 --dry-run   # no stick needed

Frames come from ffmpeg rather than OpenCV: it is one conda-forge package, it
does the V4L2 ioctls and the colour conversion, and it is not a fork of
anything. The preview is tkinter (from the `tk` package) with Pillow doing the
drawing, so cv2 is still not installed anywhere.

Upstream's camera sample cannot be carried over as-is: current ncappzoo drives
OpenVINO's MYRIAD plugin with IR files, which is NCS2 territory, and it ships no
NCS1 .graph blobs at all. This is the same idea against a graph that loads.
"""

import argparse
import http.server
import os
import shutil
import subprocess
import sys
import threading
import time

import numpy
from PIL import Image, ImageDraw

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


def overlay(img, lines):
    """Draw the labels onto a copy of the frame."""
    img = img.copy()
    d = ImageDraw.Draw(img, "RGBA")
    if lines:
        w = max(d.textlength(t) for t in lines)
        d.rectangle([0, 0, w + 12, 6 + 14 * len(lines)], fill=(0, 0, 0, 140))
        for i, text in enumerate(lines):
            d.text((6, 4 + 14 * i), text, fill=(120, 255, 120, 255))
    return img


class WindowPreview:
    """A tkinter window: frames plus the top-k line, like imshow but no cv2."""

    def __init__(self, size):
        import tkinter
        from PIL import ImageTk
        self._tk = tkinter
        self._photo_class = ImageTk.PhotoImage
        self.root = tkinter.Tk()
        self.root.title("NCSv1-camera")
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.label = tkinter.Label(self.root, borderwidth=0)
        self.label.pack()
        self.photo = None

    def show(self, img, lines):
        self.photo = self._photo_class(overlay(img, lines))
        self.label.configure(image=self.photo)
        try:
            self.root.update()
            return True
        except self._tk.TclError:
            return False

    def close(self):
        try:
            self.root.destroy()
        except Exception:
            pass


class HttpPreview:
    """The same frames as a local MJPEG page, for when there is no display."""

    def __init__(self, port):
        self.lock = threading.Condition()
        self.jpeg = None
        self.n = 0
        self.stop = False
        preview = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                if self.path in ("/", "/index.html"):
                    page = (b"<!doctype html><title>NCSv1-camera</title>"
                            b"<body style='margin:0;background:#111'>"
                            b"<img src='/stream' style='max-width:100%%'>"
                            b"<p style='color:#8f8;font:12px monospace;padding:6px'>"
                            b"what the stick sees</p>")
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(page)))
                    self.end_headers()
                    self.wfile.write(page)
                    return
                if self.path != "/stream":
                    self.send_error(404)
                    return
                self.send_response(200)
                self.send_header("Content-Type",
                                 "multipart/x-mixed-replace; boundary=frame")
                self.end_headers()
                seen = -1
                while not preview.stop:
                    with preview.lock:
                        preview.lock.wait_for(
                            lambda: preview.n != seen or preview.stop, timeout=5)
                        data, seen = preview.jpeg, preview.n
                    if data is None or preview.stop:
                        continue
                    try:
                        self.wfile.write(_part(data))
                    except (BrokenPipeError, ConnectionResetError):
                        return

        try:
            self.server = http.server.ThreadingHTTPServer(("127.0.0.1", port), Handler)
        except OSError as e:
            raise SystemExit("cannot listen on 127.0.0.1:%d (%s)" % (port, e))
        self.server.daemon_threads = True
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = "http://127.0.0.1:%d/" % self.server.server_address[1]

    def show(self, img, lines):
        buf = _jpeg(overlay(img, lines))
        with self.lock:
            self.jpeg = buf
            self.n += 1
            self.lock.notify_all()
        return True

    def close(self):
        self.stop = True
        with self.lock:
            self.lock.notify_all()
        self.server.shutdown()
        self.server.server_close()


def _part(data):
    """One frame of a multipart/x-mixed-replace stream."""
    return (b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: " +
            str(len(data)).encode() + b"\r\n\r\n" + data + b"\r\n")


def _jpeg(img, quality=70):
    from io import BytesIO
    buf = BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=quality)
    return buf.getvalue()


def open_preview(mode, size, port):
    if mode == "off":
        return None
    if mode == "http":
        p = HttpPreview(port)
        print("preview: %s  (open it in a browser; ctrl-c stops both)" % p.url)
        return p
    try:
        return WindowPreview(size)
    except Exception as e:
        print("preview: no window (%s)" % str(e).split("\n")[0])
        print("  --preview http  serves the same frames at 127.0.0.1, no display needed")
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default="/dev/video0",
                    help="camera device, video file, or lavfi:pattern")
    ap.add_argument("--graph", default="models/inception_v1.graph")
    ap.add_argument("--labels", default="models/categories.txt")
    ap.add_argument("--size", type=int, default=224, help="what the stick sees")
    ap.add_argument("--preview", choices=("window", "http", "off"), default="window")
    ap.add_argument("--preview-size", type=int, default=384)
    ap.add_argument("--preview-port", type=int, default=8099)
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
    preview = open_preview(args.preview, args.preview_size, args.preview_port)
    frames = Frames(args.source, args.size)
    start = time.perf_counter()
    n = 0
    infer_ms = 0.0
    try:
        for frame in frames:
            n += 1
            x = (frame.astype(numpy.float32) - args.mean) * args.std
            lines = []
            if not args.dry_run:
                t0 = time.perf_counter()
                graph.LoadTensor(ncs1env.tensor(x), "frame")
                out, _ = graph.GetResult()
                infer_ms += (time.perf_counter() - t0) * 1000.0
                if out is not None:
                    order = numpy.array(out, dtype=numpy.float32).argsort()[::-1]
                    lines = ["%s %.2f" % (labels[i] if i < len(labels) else i,
                                          float(out[i])) for i in order[:args.topk]]
                    speed = n / (time.perf_counter() - start)
                    sys.stdout.write("\rframe %-5d %6.1f ms %5.1f/s  %s\x1b[K" %
                                     (n, infer_ms / n, speed, "  ".join(lines)))
                    sys.stdout.flush()
            elif n == 1:
                print("frame 0: %s -> %d bytes fp16, mean %.2f, range %.2f..%.2f"
                      % (frame.shape, x.size * 2, float(x.mean()),
                         float(x.min()), float(x.max())))

            if preview:
                img = Image.fromarray(frame).resize(
                    (args.preview_size, args.preview_size), Image.BILINEAR)
                if not preview.show(img, lines):
                    preview = None
            if args.frames and n >= args.frames:
                break
    except KeyboardInterrupt:
        pass
    finally:
        elapsed = time.perf_counter() - start
        frames.close()
        if preview:
            preview.close()
        if not args.dry_run:
            if graph:
                graph.DeallocateGraph()
            if device:
                device.CloseDevice()

    if not args.dry_run:
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
