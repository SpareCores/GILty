"""A word-level Markov chain: train on a text, then babble in its style.

An order-k model maps the last k words to every word that followed them in
the text (repeats keep the frequencies). Babbling walks the chain: look up
the current state, pick one of its followers at random, shift the state,
repeat. Every lookup depends on the previous one, and the model of a novel
is a hash table of tens of thousands of states (order 1) to a couple of
hundred thousand (order 3): the work is chasing pointers through megabytes,
one step at a time, on one core.
"""

import gzip
import importlib.resources
import random


def load_book(name="moby-dick"):
    """The text of a bundled book."""
    data = importlib.resources.files("gilty.data").joinpath(f"{name}.txt.gz").read_bytes()
    return gzip.decompress(data).decode("utf-8")


def tokenize(text):
    """Words as they appear, punctuation attached ("whale," and "whale."
    are different words, which keeps sentences and commas in the babble)."""
    return text.split()


def train(tokens, order=2):
    """The model: {state: [followers]}; a state is a word (order 1) or a
    tuple of words."""
    model = {}
    if order == 1:
        for a, b in zip(tokens, tokens[1:]):
            model.setdefault(a, []).append(b)
    elif order == 2:
        for a, b, c in zip(tokens, tokens[1:], tokens[2:]):
            model.setdefault((a, b), []).append(c)
    else:
        for i in range(len(tokens) - order):
            model.setdefault(tuple(tokens[i : i + order]), []).append(tokens[i + order])
    return model


class Babbler:
    """Walks a model; babble(n) advances n words and returns the last few."""

    def __init__(self, model, order, tokens, seed=None):
        self.model = model
        self.order = order
        self.rng = random.Random(seed)
        # restart points: sentence starts in the text
        self.starts = [
            tuple(tokens[i + 1 : i + 1 + order]) if order > 1 else tokens[i + 1]
            for i in range(len(tokens) - order - 1)
            if tokens[i].endswith(".") and tokens[i + 1][:1].isupper()
        ]
        self.state = self.rng.choice(self.starts)
        self.words = 0

    def babble(self, n, keep=40):
        """Generate n words; returns the last `keep` of them."""
        model, rnd, state = self.model, self.rng.random, self.state
        tail = []
        push = tail.append
        if self.order == 1:
            for _ in range(n):
                follow = model.get(state)
                if follow is None:  # the last word of the book
                    state = self.rng.choice(self.starts)
                    continue
                state = follow[int(rnd() * len(follow))]
                push(state)
        elif self.order == 2:
            a, b = state
            for _ in range(n):
                follow = model.get((a, b))
                if follow is None:
                    a, b = self.rng.choice(self.starts)
                    continue
                a, b = b, follow[int(rnd() * len(follow))]
                push(b)
            state = (a, b)
        else:
            for _ in range(n):
                follow = model.get(state)
                if follow is None:
                    state = self.rng.choice(self.starts)
                    continue
                state = state[1:] + (follow[int(rnd() * len(follow))],)
                push(state[-1])
        self.state = state
        self.words += n
        return tail[-keep:]
