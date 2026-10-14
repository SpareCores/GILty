"""Candidate GILty workloads, timed on one core.

Each kernel runs at several working-set sizes; the output is one JSON line per
(kernel, size) with the best of three runs, so that runs on two machines can
be compared kernel by kernel. Plain CPython, no third-party packages.

    python3 kernels.py [--quick] > results.jsonl
"""

import array
import gc
import json
import platform
import random
import sys
import time


def best_of(fn, repeat=3):
    best = None
    for _ in range(repeat):
        gc.collect()
        t = time.perf_counter()
        fn()
        dt = time.perf_counter() - t
        best = dt if best is None or dt < best else best
    return best


# --- interpreter-bound -------------------------------------------------------


def mandelbrot(n):
    """Escape-time Mandelbrot on an n x n grid, plain floats."""

    def run():
        total = 0
        for y in range(n):
            ci = -1.2 + 2.4 * y / n
            for x in range(n):
                cr = -2.0 + 2.8 * x / n
                zr = zi = 0.0
                i = 0
                while i < 200 and zr * zr + zi * zi < 4.0:
                    zr, zi = zr * zr - zi * zi + cr, 2.0 * zr * zi + ci
                    i += 1
                total += i
        return total

    return run


def nbody(steps):
    bodies = [[random.random() for _ in range(7)] for _ in range(5)]

    def run():
        for _ in range(steps):
            for i in range(5):
                bi = bodies[i]
                for j in range(i + 1, 5):
                    bj = bodies[j]
                    dx, dy, dz = bi[0] - bj[0], bi[1] - bj[1], bi[2] - bj[2]
                    d2 = dx * dx + dy * dy + dz * dz + 0.01
                    mag = 0.001 / (d2 * d2**0.5)
                    bi[3] -= dx * bj[6] * mag
                    bj[3] += dx * bi[6] * mag
            for b in bodies:
                b[0] += 0.001 * b[3]

    return run


# --- memory-bound, sized ------------------------------------------------------


def list_sum(n):
    """Sequential walk over n float objects (allocated in order)."""
    data = [float(i) for i in range(n)]
    return lambda: sum(data)


def list_shuffled_sum(n):
    """The same walk over objects in random memory order (latency-bound)."""
    data = [float(i) for i in range(n)]
    random.shuffle(data)
    return lambda: sum(data)


def array_scan(n):
    """A typed array of n doubles: C loop over contiguous memory."""
    data = array.array("d", range(n))
    return lambda: sum(data)


def bytes_ops(n):
    """Byte-buffer passes: translate, count, copy (memcpy-like) over n bytes."""
    buf = bytes(random.getrandbits(8) for _ in range(min(n, 1 << 16))) * max(1, n >> 16)
    table = bytes(range(255, -1, -1))

    def run():
        b = buf.translate(table)
        b.count(b"\x00")
        bytearray(b)[1:] + b[:1]

    return run


def dict_lookup(n):
    """n-key dict, lookups in random order (hash table larger than caches)."""
    d = {i * 7919: i for i in range(n)}
    keys = [i * 7919 for i in range(n)]
    random.shuffle(keys)

    def run():
        s = 0
        for k in keys:
            s += d[k]
        return s

    return run


def sort_floats(n):
    data = [random.random() for _ in range(n)]
    return lambda: sorted(data)


def grid_stencil(n):
    """Pure-Python 4-neighbour blur over an n x n list-of-lists image."""
    img = [[random.random() for _ in range(n)] for _ in range(n)]

    def run():
        out = [[0.0] * n for _ in range(n)]
        for y in range(1, n - 1):
            up, row, down, o = img[y - 1], img[y], img[y + 1], out[y]
            for x in range(1, n - 1):
                o[x] = 0.25 * (up[x] + down[x] + row[x - 1] + row[x + 1])
        return out

    return run


SIZED = {
    # elements; float objects are 24 B + an 8 B pointer
    "list_sum": [10_000, 100_000, 1_000_000, 10_000_000],
    "list_shuffled_sum": [10_000, 100_000, 1_000_000, 10_000_000],
    "array_scan": [10_000, 100_000, 1_000_000, 10_000_000],
    "bytes_ops": [1 << 16, 1 << 20, 1 << 24, 1 << 27],
    "dict_lookup": [10_000, 100_000, 1_000_000, 4_000_000],
    "sort_floats": [10_000, 100_000, 1_000_000, 4_000_000],
    "grid_stencil": [100, 300, 1000, 2000],
}
FIXED = {"mandelbrot": (mandelbrot, 300), "nbody": (nbody, 100_000)}


def main():
    quick = "--quick" in sys.argv
    meta = {"python": platform.python_version(), "machine": platform.machine()}
    for name, (make, arg) in FIXED.items():
        dt = best_of(make(arg // (10 if quick else 1)))
        print(json.dumps({"kernel": name, "size": arg, "seconds": dt, **meta}), flush=True)
    for name, sizes in SIZED.items():
        make = globals()[name]
        for n in sizes[:2] if quick else sizes:
            fn = make(n)
            dt = best_of(fn)
            # normalise to a fixed amount of work: seconds per million elements
            print(json.dumps({"kernel": name, "size": n, "seconds": dt, "per_million": dt / n * 1e6, **meta}), flush=True)
            del fn


if __name__ == "__main__":
    main()
