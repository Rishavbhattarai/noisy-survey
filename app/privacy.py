"""Randomized-response mechanisms and their unbiased estimators.

Two schemes are supported:

Forced response
    With probability ``p_truth`` the respondent's true answer is recorded.
    Otherwise the answer is forced: "yes" with probability ``p_yes`` and
    "no" with probability ``p_no = 1 - p_truth - p_yes``.

        P(reported yes) = p_truth * pi + p_yes
        pi_hat          = (lambda_hat - p_yes) / p_truth

Warner
    With probability ``p`` the true answer is recorded, otherwise its
    opposite. Requires ``p != 0.5`` (at 0.5 the answer carries no signal).

        P(reported yes) = p * pi + (1 - p) * (1 - pi)
        pi_hat          = (lambda_hat - (1 - p)) / (2p - 1)

Here ``pi`` is the true share of "yes" in the population and ``lambda_hat``
is the observed share of "yes" among the stored (noisy) answers.
"""

import math
import random
from dataclasses import dataclass

Z_95 = 1.96
_TOL = 1e-9


@dataclass(frozen=True)
class Estimate:
    n: int
    raw_rate: float  # observed share of "yes" in the noisy data (lambda_hat)
    pi_hat: float  # corrected estimate of the true share of "yes"
    se: float
    ci_low: float
    ci_high: float


# --- parameter validation -------------------------------------------------


def _check_prob(name: str, value: float) -> None:
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"{name} must be in [0, 1], got {value}")


def validate_forced(p_truth: float, p_yes: float) -> float:
    """Validate forced-response parameters and return the implied p_no."""
    _check_prob("p_truth", p_truth)
    _check_prob("p_yes", p_yes)
    if p_truth <= 0.0:
        raise ValueError("p_truth must be > 0, otherwise answers carry no signal")
    p_no = 1.0 - p_truth - p_yes
    if p_no < -_TOL:
        raise ValueError(f"p_truth + p_yes must be <= 1, got {p_truth + p_yes}")
    # snap float residue (e.g. 1 - 0.7 - 0.3 == 5.5e-17) to an exact 0
    return 0.0 if p_no < _TOL else p_no


def validate_warner(p: float) -> None:
    _check_prob("p", p)
    if abs(p - 0.5) < _TOL:
        raise ValueError("Warner p must not be 0.5, otherwise answers carry no signal")


def _check_counts(yes_count: int, n: int) -> None:
    if n <= 0:
        raise ValueError("n must be > 0 to estimate anything")
    if not 0 <= yes_count <= n:
        raise ValueError(f"yes_count must be in [0, n], got {yes_count} of {n}")


# --- mechanisms (applied to each answer before it is stored) ---------------


def randomize_forced(
    true_answer: bool, p_truth: float, p_yes: float, rng: random.Random | None = None
) -> bool:
    validate_forced(p_truth, p_yes)
    rng = rng or random.SystemRandom()
    r = rng.random()
    if r < p_truth:
        return true_answer
    if r < p_truth + p_yes:
        return True
    return False


def randomize_warner(true_answer: bool, p: float, rng: random.Random | None = None) -> bool:
    validate_warner(p)
    rng = rng or random.SystemRandom()
    return true_answer if rng.random() < p else not true_answer


# --- estimators (applied to the aggregated noisy answers) -----------------


def _clip(x: float) -> float:
    return min(1.0, max(0.0, x))


def _build(n: int, raw: float, pi_hat: float, se: float) -> Estimate:
    return Estimate(
        n=n,
        raw_rate=raw,
        pi_hat=_clip(pi_hat),
        se=se,
        ci_low=_clip(pi_hat - Z_95 * se),
        ci_high=_clip(pi_hat + Z_95 * se),
    )


def estimate_forced(yes_count: int, n: int, p_truth: float, p_yes: float) -> Estimate:
    validate_forced(p_truth, p_yes)
    _check_counts(yes_count, n)
    raw = yes_count / n
    pi_hat = (raw - p_yes) / p_truth
    se = math.sqrt(raw * (1 - raw) / n) / p_truth
    return _build(n, raw, pi_hat, se)


def estimate_warner(yes_count: int, n: int, p: float) -> Estimate:
    validate_warner(p)
    _check_counts(yes_count, n)
    raw = yes_count / n
    pi_hat = (raw - (1 - p)) / (2 * p - 1)
    se = math.sqrt(raw * (1 - raw) / n) / abs(2 * p - 1)
    return _build(n, raw, pi_hat, se)


# --- privacy guarantee ------------------------------------------------------


def _log_ratio(a: float, b: float) -> float:
    if a == 0.0 and b == 0.0:
        return 0.0
    if a == 0.0 or b == 0.0:
        return math.inf
    return abs(math.log(a / b))


def epsilon_forced(p_truth: float, p_yes: float) -> float:
    """Local differential privacy epsilon: the worst-case log ratio of how
    likely a reported answer is under a true "yes" versus a true "no"."""
    p_no = validate_forced(p_truth, p_yes)
    return max(
        _log_ratio(p_truth + p_yes, p_yes),  # reported "yes"
        _log_ratio(p_truth + p_no, p_no),  # reported "no"
    )


def epsilon_warner(p: float) -> float:
    validate_warner(p)
    return _log_ratio(p, 1 - p)
