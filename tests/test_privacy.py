import math
import random

import pytest

from app.privacy import (
    epsilon_forced,
    epsilon_warner,
    estimate_forced,
    estimate_warner,
    randomize_forced,
    randomize_warner,
)

N = 20_000
TRUE_RATE = 0.2


def _population(rng: random.Random, n: int, true_rate: float) -> list[bool]:
    return [rng.random() < true_rate for _ in range(n)]


# --- simulation: the estimators recover the true rate -----------------------


@pytest.mark.parametrize("p_truth,p_yes", [(0.4, 0.3), (0.6, 0.2), (0.8, 0.1)])
def test_forced_recovers_true_rate(p_truth, p_yes):
    rng = random.Random(42)
    reported = [randomize_forced(a, p_truth, p_yes, rng) for a in _population(rng, N, TRUE_RATE)]
    est = estimate_forced(sum(reported), N, p_truth, p_yes)

    assert abs(est.pi_hat - TRUE_RATE) < 3 * est.se
    assert est.ci_low <= TRUE_RATE <= est.ci_high
    # the raw noisy rate is biased towards p_yes, so it should be clearly off
    assert abs(est.raw_rate - TRUE_RATE) > 3 * est.se


@pytest.mark.parametrize("p", [0.7, 0.8, 0.25])
def test_warner_recovers_true_rate(p):
    rng = random.Random(7)
    reported = [randomize_warner(a, p, rng) for a in _population(rng, N, TRUE_RATE)]
    est = estimate_warner(sum(reported), N, p)

    assert abs(est.pi_hat - TRUE_RATE) < 3 * est.se
    assert est.ci_low <= TRUE_RATE <= est.ci_high


# --- mechanisms behave as specified ----------------------------------------


def test_forced_no_respondent_says_yes_at_p_yes():
    rng = random.Random(1)
    draws = 50_000
    yes = sum(randomize_forced(False, 0.5, 0.3, rng) for _ in range(draws))
    assert yes / draws == pytest.approx(0.3, abs=0.01)


def test_forced_yes_respondent_says_yes_at_p_truth_plus_p_yes():
    rng = random.Random(2)
    draws = 50_000
    yes = sum(randomize_forced(True, 0.5, 0.3, rng) for _ in range(draws))
    assert yes / draws == pytest.approx(0.8, abs=0.01)


def test_warner_flips_at_one_minus_p():
    rng = random.Random(3)
    draws = 50_000
    flipped = sum(randomize_warner(True, 0.75, rng) is False for _ in range(draws))
    assert flipped / draws == pytest.approx(0.25, abs=0.01)


def test_mechanism_works_without_explicit_rng():
    assert randomize_forced(True, 0.5, 0.3) in (True, False)
    assert randomize_warner(True, 0.75) in (True, False)


# --- estimator math and edge cases -----------------------------------------


def test_forced_estimate_exact_value():
    # lambda = 0.5, pi_hat = (0.5 - 0.3) / 0.4 = 0.5
    est = estimate_forced(50, 100, p_truth=0.4, p_yes=0.3)
    assert est.raw_rate == pytest.approx(0.5)
    assert est.pi_hat == pytest.approx(0.5)
    assert est.se == pytest.approx(math.sqrt(0.25 / 100) / 0.4)


def test_warner_estimate_exact_value():
    # lambda = 0.4, pi_hat = (0.4 - 0.25) / 0.5 = 0.3
    est = estimate_warner(40, 100, p=0.75)
    assert est.pi_hat == pytest.approx(0.3)


def test_estimates_are_clipped_to_unit_interval():
    # 10% yes is below the forced-yes floor of 30%, so the raw estimate is negative
    low = estimate_forced(10, 100, p_truth=0.4, p_yes=0.3)
    assert low.pi_hat == 0.0 and low.ci_low == 0.0
    high = estimate_warner(100, 100, p=0.75)
    assert high.pi_hat == 1.0 and high.ci_high == 1.0


@pytest.mark.parametrize(
    "call",
    [
        lambda: estimate_forced(0, 0, 0.5, 0.3),  # n == 0
        lambda: estimate_forced(11, 10, 0.5, 0.3),  # yes_count > n
        lambda: estimate_warner(5, 10, 0.5),  # Warner p == 0.5
        lambda: estimate_forced(5, 10, 0.0, 0.5),  # p_truth == 0
        lambda: estimate_forced(5, 10, 0.8, 0.3),  # probabilities > 1
        lambda: randomize_forced(True, -0.1, 0.3),  # negative probability
        lambda: randomize_warner(True, 1.5),  # probability > 1
    ],
)
def test_invalid_parameters_raise(call):
    with pytest.raises(ValueError):
        call()


# --- privacy guarantee ------------------------------------------------------


def test_epsilon_forced():
    # P(yes|yes)=0.7, P(yes|no)=0.3; P(no|no)=0.7, P(no|yes)=0.3 -> ln(7/3)
    assert epsilon_forced(0.4, 0.3) == pytest.approx(math.log(0.7 / 0.3))


def test_epsilon_forced_is_infinite_without_forced_no():
    # with p_no = 0 a reported "no" proves the true answer was "no"
    assert epsilon_forced(0.7, 0.3) == math.inf


def test_epsilon_warner_is_symmetric():
    assert epsilon_warner(0.75) == pytest.approx(math.log(3))
    assert epsilon_warner(0.25) == pytest.approx(math.log(3))


def test_more_noise_means_smaller_epsilon():
    assert epsilon_warner(0.6) < epsilon_warner(0.9)
    assert epsilon_forced(0.2, 0.4) < epsilon_forced(0.8, 0.1)
