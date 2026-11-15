"""Learning from your feedback: a small reward model trained on your own decisions.

Every decision is a reward signal: saving, drafting or applying to a job is positive; an
application that led to an interview or offer is a stronger positive; marking a job "not
relevant" is negative. A logistic-regression model learns which score parts (skills, role,
wording, meaning-based similarity, similar titles, "apply yourself") predict *your* positive
decisions, and nudges each job's match score by up to ±10 points.

This is reward-based learning in the practical sense for one person's data (online,
explainable, retrained from scratch on every change, all local). It is not deep reinforcement
learning and it never changes a language model: with tens of decisions, a transparent linear
model is the method that actually works and can be explained.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

FEATURES = ("skills", "role", "wording", "semantic", "titles", "manual")
MIN_LABELS = 6
MIN_PER_CLASS = 2
POINTS = 10


@dataclass(frozen=True)
class Model:
    weights: tuple[float, ...]
    bias: float
    labels: int

    def probability(self, x: list[float]) -> float:
        z = self.bias + sum(w * v for w, v in zip(self.weights, x, strict=True))
        return 1 / (1 + math.exp(-max(-30.0, min(30.0, z))))

    def adjustment(self, x: list[float]) -> int:
        return max(-POINTS, min(POINTS, round(2 * POINTS * (self.probability(x) - 0.5))))


def features(parts: dict, semantic: float | None, apply_manually: bool) -> list[float]:
    return [
        parts.get("skills", 0) / 60,
        parts.get("role", 0) / 25,
        parts.get("wording", 0) / 15,
        semantic if semantic is not None else 0.5,
        parts.get("feedback", 0) / 10,
        1.0 if apply_manually else 0.0,
    ]


def train(samples: list[tuple[list[float], int, float]], epochs: int = 400, rate: float = 0.5,
          l2: float = 0.05) -> Model | None:
    """samples: (features, label 0/1, weight). Returns None until there are enough decisions."""
    positives = sum(1 for _, y, _ in samples if y == 1)
    negatives = len(samples) - positives
    if len(samples) < MIN_LABELS or positives < MIN_PER_CLASS or negatives < MIN_PER_CLASS:
        return None
    n = len(FEATURES)
    w = [0.0] * n
    b = 0.0
    total = sum(weight for _, _, weight in samples)
    for _ in range(epochs):
        gw = [0.0] * n
        gb = 0.0
        for x, y, weight in samples:
            z = b + sum(wi * xi for wi, xi in zip(w, x, strict=True))
            p = 1 / (1 + math.exp(-max(-30.0, min(30.0, z))))
            error = (p - y) * weight
            for i in range(n):
                gw[i] += error * x[i]
            gb += error
        for i in range(n):
            w[i] -= rate * (gw[i] / total + l2 * w[i])
        b -= rate * gb / total
    return Model(tuple(w), b, len(samples))
