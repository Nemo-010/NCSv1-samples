"""Small cross-platform helpers: paths, hashes, verified downloads, tar members.

Standard library only, so these run the same on any host pixi supports. Nothing
here is Linux-specific; the shell was only ever accidental convenience.
"""

import hashlib
import pathlib
import sys
import tarfile
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent

# how many artefacts this run actually wrote, so setup can stay quiet when
# there is nothing to do
WORK = 0


def say(msg):
    print(msg)


def die(msg):
    print("error: %s" % msg, file=sys.stderr)
    raise SystemExit(1)


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch(url, dest, want, quiet=False):
    """Download `url` to `dest` unless it is already the file with hash `want`."""
    dest = ROOT / dest
    if dest.is_file() and sha256(dest) == want:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not quiet:
        say("fetch %s" % url)
    part = dest.with_name(dest.name + ".part")
    req = urllib.request.Request(url, headers={"User-Agent": "NCSv1-samples"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r, open(part, "wb") as f:
            while True:
                chunk = r.read(1 << 20)
                if not chunk:
                    break
                f.write(chunk)
    except Exception as e:
        part.unlink(missing_ok=True)
        die("download failed: %s (%s)" % (url, e))
    got = sha256(part)
    if got != want:
        part.unlink(missing_ok=True)
        die("sha256 mismatch for %s\n  want %s\n  got  %s" % (url, want, got))
    part.replace(dest)
    global WORK
    WORK += 1
    return dest


def tar_member(tarball, member, dest, want, label):
    """Extract one member of a tarball to `dest`, hash-checked."""
    tarball = ROOT / tarball
    dest = ROOT / dest
    if dest.is_file() and sha256(dest) == want:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + ".part")
    try:
        with tarfile.open(tarball, "r:gz") as tar:
            src = tar.extractfile(member)
            if src is None:
                die("no %s in %s" % (member, tarball))
            with open(part, "wb") as f:
                for chunk in iter(lambda: src.read(1 << 20), b""):
                    f.write(chunk)
    except KeyError:
        die("no %s in %s" % (member, tarball))
    got = sha256(part)
    if got != want:
        part.unlink(missing_ok=True)
        die("%s sha256 mismatch: want %s, got %s" % (label, want, got))
    part.chmod(0o755)
    part.replace(dest)
    global WORK
    WORK += 1
    say("%s: %s (%d bytes)" % (label, dest.relative_to(ROOT), dest.stat().st_size))
    return dest
