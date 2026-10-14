"""Prototype: maze generation and breadth-first flood, timed per maze size.

The maze graph is a dict {cell id: tuple of neighbour ids}; cell ids are a
random permutation, as in a real graph whose nodes are not laid out in visit
order, so the flood's lookups jump around memory.
"""

import gc
import json
import random
import sys
import time
from collections import deque


def make_maze(side, rng):
    n = side * side
    ids = list(range(n))
    rng.shuffle(ids)  # cell (x, y) -> scrambled id
    adj = {i: [] for i in ids}
    seen = bytearray(n)
    stack = [0]
    seen[0] = 1
    while stack:
        cell = stack[-1]
        x, y = divmod(cell, side)
        opts = []
        if x > 0 and not seen[cell - side]:
            opts.append(cell - side)
        if x < side - 1 and not seen[cell + side]:
            opts.append(cell + side)
        if y > 0 and not seen[cell - 1]:
            opts.append(cell - 1)
        if y < side - 1 and not seen[cell + 1]:
            opts.append(cell + 1)
        if not opts:
            stack.pop()
            continue
        nxt = opts[rng.randrange(len(opts))]
        seen[nxt] = 1
        adj[ids[cell]].append(ids[nxt])
        adj[ids[nxt]].append(ids[cell])
        stack.append(nxt)
    return {k: tuple(v) for k, v in adj.items()}, ids


def flood(adj, start):
    parent = {start: start}
    q = deque([start])
    pop, push = q.popleft, q.append
    while q:
        c = pop()
        for nb in adj[c]:
            if nb not in parent:
                parent[nb] = c
                push(nb)
    return parent


def main():
    sides = [int(a) for a in sys.argv[1:]] or [100, 150, 200, 250, 300, 350, 400, 500, 700]
    for side in sides:
        rng = random.Random(42)
        t = time.perf_counter()
        adj, ids = make_maze(side, rng)
        gen = time.perf_counter() - t
        best = None
        for _ in range(3):
            gc.collect()
            t = time.perf_counter()
            flood(adj, ids[0])
            dt = time.perf_counter() - t
            best = dt if best is None or dt < best else best
        print(json.dumps({"side": side, "cells": side * side, "generate": gen, "flood": best,
                          "ns_per_cell": best / side / side * 1e9}), flush=True)
        del adj, ids


if __name__ == "__main__":
    main()
