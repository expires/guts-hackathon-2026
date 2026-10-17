"""Twin matching: Mahalanobis k-nearest neighbours over person features.

Features (in order): age, log income, log savings, log debt, region latitude, region longitude,
and one-hot housing (own, mortgage, rent, parents).
Money features use log1p so a gap of 1,000 matters more at 5,000 than at 500,000.
Region uses the approximate centroid so near regions count as near.

One-hot housing makes the covariance singular (the four columns sum to 1). The inverse is
`pinv(cov + RIDGE * I)`, so a singular or near-singular covariance never fails.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from lifeline_contracts.domain import Housing
from lifeline_engine.population import TENURES, Person

FloatArray = NDArray[np.float64]

RIDGE = 1e-6

# Approximate region centroids (latitude, longitude).
REGION_CENTROIDS: dict[str, tuple[float, float]] = {
    "north-east": (55.0, -1.9),
    "north-west": (53.8, -2.7),
    "yorkshire-and-the-humber": (53.9, -1.2),
    "east-midlands": (52.9, -0.9),
    "west-midlands": (52.5, -2.2),
    "east-of-england": (52.2, 0.4),
    "london": (51.5, -0.1),
    "south-east": (51.3, -0.6),
    "south-west": (50.9, -3.6),
    "wales": (52.3, -3.8),
    "scotland": (56.8, -4.2),
    "northern-ireland": (54.6, -6.7),
}
UK_CENTROID = (54.0, -2.5)

FEATURE_NAMES: tuple[str, ...] = (
    "age",
    "log_income",
    "log_savings",
    "log_debt",
    "lat",
    "lon",
    *(f"housing_{t}" for t in TENURES),
)


def features(age: float, income: float, savings: float, debt: float, housing: Housing, region: str) -> FloatArray:
    """Feature vector for one person. Unknown regions use the UK centroid."""
    lat, lon = REGION_CENTROIDS.get(region, UK_CENTROID)
    onehot = [1.0 if housing == t else 0.0 for t in TENURES]
    return np.array(
        [
            float(age),
            np.log1p(max(0.0, income)),
            np.log1p(max(0.0, savings)),
            np.log1p(max(0.0, debt)),
            lat,
            lon,
            *onehot,
        ],
        dtype=np.float64,
    )


def person_features(p: Person) -> FloatArray:
    return features(p.age, p.annual_income, p.savings, p.debt, p.housing, p.region)


@dataclass(frozen=True)
class Twin:
    index: int
    distance: float
    person: Person


@dataclass(frozen=True)
class TwinIndex:
    """Precomputed feature matrix and inverse covariance for a fixed population."""

    people: tuple[Person, ...]
    matrix: FloatArray
    inv_cov: FloatArray

    @classmethod
    def build(cls, people: Sequence[Person]) -> TwinIndex:
        if not people:
            raise ValueError("population is empty")
        matrix = np.vstack([person_features(p) for p in people])
        return cls(people=tuple(people), matrix=matrix, inv_cov=inverse_covariance(matrix))

    def distances(self, target: FloatArray) -> FloatArray:
        diff = self.matrix - target[None, :]
        d2 = np.einsum("ij,jk,ik->i", diff, self.inv_cov, diff)
        out: FloatArray = np.sqrt(np.maximum(d2, 0.0))
        return out

    def nearest(self, target: FloatArray, k: int) -> list[Twin]:
        """k nearest people. Ties break on population index, so the result is deterministic."""
        if k <= 0:
            return []
        d = self.distances(target)
        order = np.lexsort((np.arange(d.size), d))[:k]
        return [Twin(index=int(i), distance=float(d[i]), person=self.people[int(i)]) for i in order]


def inverse_covariance(matrix: FloatArray) -> FloatArray:
    """Pseudo-inverse of the ridge-regularised sample covariance. Safe for singular data."""
    n, dims = matrix.shape
    cov = np.cov(matrix, rowvar=False) if n > 1 else np.zeros((dims, dims))
    cov = np.atleast_2d(np.asarray(cov, dtype=np.float64))
    result: FloatArray = np.linalg.pinv(cov + RIDGE * np.eye(dims), hermitian=True)
    return result


def find_twins(target: Person, people: Sequence[Person], k: int) -> list[Twin]:
    """Convenience wrapper: build an index and return the k nearest twins of `target`."""
    return TwinIndex.build(people).nearest(person_features(target), k)
