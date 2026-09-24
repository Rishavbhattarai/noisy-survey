import random

import pytest

from app.db import add_question, count_responses
from app.results import all_results
from scripts.simulate import reset_responses, simulate


def test_simulate_adds_n_responses_per_question(conn):
    a = add_question(conn, "A?", "forced", p_truth=0.5, p_yes=0.3)
    b = add_question(conn, "B?", "warner", warner_p=0.75)
    simulate(conn, 200, 0.3, rng=random.Random(1))
    assert count_responses(conn, a.id)[1] == 200
    assert count_responses(conn, b.id)[1] == 200


def test_simulate_only_selected_questions(conn):
    a = add_question(conn, "A?", "warner", warner_p=0.75)
    b = add_question(conn, "B?", "warner", warner_p=0.75)
    simulate(conn, 50, 0.3, question_ids=[b.id], rng=random.Random(1))
    assert count_responses(conn, a.id)[1] == 0
    assert count_responses(conn, b.id)[1] == 50


def test_simulated_data_recovers_true_rate(conn):
    add_question(conn, "A?", "forced", p_truth=0.5, p_yes=0.3)
    add_question(conn, "B?", "warner", warner_p=0.8)
    simulate(conn, 4000, 0.15, rng=random.Random(9))
    for r in all_results(conn):
        assert r.estimate.ci_low <= 0.15 <= r.estimate.ci_high


def test_reset_clears_responses(conn):
    q = add_question(conn, "A?", "warner", warner_p=0.75)
    simulate(conn, 10, 0.5, rng=random.Random(1))
    reset_responses(conn)
    assert count_responses(conn, q.id) == (0, 0)


@pytest.mark.parametrize(
    "kwargs",
    [dict(n=0, true_rate=0.5), dict(n=10, true_rate=1.5), dict(n=10, true_rate=0.5, question_ids=[999])],
)
def test_simulate_rejects_bad_input(conn, kwargs):
    add_question(conn, "A?", "warner", warner_p=0.75)
    with pytest.raises(ValueError):
        simulate(conn, **kwargs)
