"""Natural program shapes whose hot loop is mostly dict lookups.

  social    level-synchronous BFS over a random graph ("six degrees"): adjacency
            dict id -> tuple, distance dict pre-filled with -1 and only updated
            (levels stay small, so no new int objects, no table growth)
  chaos     chaos-game fractal: points jump between attractor corners, each hit
            increments a pixel in a dict canvas keyed by y * W + x
  spell     spell-check: words of a text looked up in a vocabulary set
"""

import gc
import json
import random
import string
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


def social(n, degree=6):
    rng = random.Random(3)
    ids = list(range(n))
    rng.shuffle(ids)
    friends = {i: set() for i in ids}
    for _ in range(n * degree // 2):
        a, b = rng.randrange(n), rng.randrange(n)
        if a != b:
            friends[a].add(b)
            friends[b].add(a)
    adj = {i: tuple(friends[i]) for i in ids}
    del friends

    def run():
        dist = dict.fromkeys(adj, -1)
        frontier = [ids[0]]
        dist[ids[0]] = 0
        level = 0
        while frontier:
            level += 1
            nxt = []
            for c in frontier:
                for f in adj[c]:
                    if dist[f] < 0:
                        dist[f] = level
                        nxt.append(f)
            frontier = nxt
        return level

    return run, n


def chaos(side, points=400_000):
    corners = [(side / 2, 0.0), (0.0, side - 1.0), (side - 1.0, side - 1.0)]
    canvas = {y * side + x: 0 for y in range(side) for x in range(side)}
    rng = random.Random(5)
    picks = [corners[rng.randrange(3)] for _ in range(points)]

    def run():
        x, y = side / 3, side / 3
        c = canvas
        for cx, cy in picks:
            x = (x + cx) * 0.5
            y = (y + cy) * 0.5
            k = int(y) * side + int(x)
            c[k] += 1

    return run, points


def spell(vocab_size, text_words=400_000):
    rng = random.Random(9)
    letters = string.ascii_lowercase
    vocab = {"".join(rng.choice(letters) for _ in range(rng.randrange(4, 11))) for _ in range(vocab_size)}
    words = list(vocab)
    text = [("".join(rng.choice(letters) for _ in range(6)) if rng.random() < 0.05 else rng.choice(words))
            for _ in range(text_words)]
    text = [w[:1] + w[1:] for w in text]  # fresh string objects, as if parsed

    def run():
        bad = 0
        for w in text:
            if w not in vocab:
                bad += 1
        return bad

    return run, text_words


CASES = [
    ("social", social, [50_000, 100_000, 150_000, 250_000, 400_000]),
    ("chaos", chaos, [200, 300, 400, 500, 700]),
    ("spell", spell, [50_000, 100_000, 200_000, 400_000]),
]


def main():
    for name, make, sizes in CASES:
        for size in sizes:
            run, work = make(size)
            dt = best_of(run)
            print(json.dumps({"program": name, "size": size, "seconds": dt, "ns": dt / work * 1e9}), flush=True)
            del run


if __name__ == "__main__":
    main()
