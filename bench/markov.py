"""Markov-chain text generation: train on a corpus, then babble.

The corpus comes from a hidden "true" language: V pronounceable pseudo-words,
each followed by a few likely successors (Zipf-like). An order-k model maps
the last k words (a str, or a tuple of str for k = 2) to the list of words
that followed them in the corpus (repeats keep the frequencies), and
generation walks the chain: every step looks up the current state, picks a
successor at random and moves on, so each lookup depends on the previous one.

    python3 markov.py  ->  JSON lines: order, vocabulary, states, train and
                           generate seconds, ns per generated word
"""

import gc
import json
import random
import sys
import time

SYLLABLES = [c + v for c in "bdfgklmnprstvz" for v in "aeiou"] + ["ch", "sh", "th", "qu"]


def vocabulary(n, rng):
    words = set()
    while len(words) < n:
        words.add("".join(rng.choice(SYLLABLES) for _ in range(rng.randrange(2, 5))))
    return sorted(words)


def corpus(words, length, rng, fanout=12):
    """A walk over a sparse random transition graph with skewed weights."""
    n = len(words)
    nxt = [[rng.randrange(n) for _ in range(fanout)] for _ in range(n)]
    weights = [1.0 / (i + 1) for i in range(fanout)]
    out = []
    w = rng.randrange(n)
    for _ in range(length):
        out.append(words[w])
        w = rng.choices(nxt[w], weights)[0] if rng.random() < 0.97 else rng.randrange(n)
    return out


def train(tokens, order):
    model = {}
    if order == 1:
        for a, b in zip(tokens, tokens[1:]):
            model.setdefault(a, []).append(b)
    else:
        for a, b, c in zip(tokens, tokens[1:], tokens[2:]):
            model.setdefault((a, b), []).append(c)
    return model


def generate(model, order, start, n, rng):
    rnd = rng.random
    state = start
    out = []
    push = out.append
    if order == 1:
        for _ in range(n):
            succ = model.get(state)
            if succ is None:
                state = start
                continue
            state = succ[int(rnd() * len(succ))]
            push(state)
    else:
        a, b = start
        for _ in range(n):
            succ = model.get((a, b))
            if succ is None:
                a, b = start
                continue
            a, b = b, succ[int(rnd() * len(succ))]
            push(b)
    return out


def main():
    configs = [  # (order, vocabulary, corpus words)
        (1, 30_000, 600_000),
        (1, 100_000, 2_000_000),
        (1, 300_000, 4_000_000),
        (2, 5_000, 600_000),
        (2, 10_000, 1_500_000),
        (2, 20_000, 3_000_000),
        (2, 40_000, 5_000_000),
    ]
    if len(sys.argv) > 1:
        configs = [tuple(int(x) for x in a.split(",")) for a in sys.argv[1:]]
    for order, vocab, length in configs:
        rng = random.Random(11)
        words = vocabulary(vocab, rng)
        tokens = corpus(words, length, rng)
        gc.collect()
        t = time.perf_counter()
        model = train(tokens, order)
        train_s = time.perf_counter() - t
        start = tokens[0] if order == 1 else (tokens[0], tokens[1])
        n = 1_000_000
        best = None
        for _ in range(3):
            gc.collect()
            t = time.perf_counter()
            generate(model, order, start, n, random.Random(3))
            dt = time.perf_counter() - t
            best = dt if best is None or dt < best else best
        print(json.dumps({"order": order, "vocabulary": vocab, "corpus": length, "states": len(model),
                          "train": round(train_s, 3), "generate": round(best, 3), "ns_per_word": round(best / n * 1e9, 1)}),
              flush=True)
        del model, tokens, words


if __name__ == "__main__":
    main()
