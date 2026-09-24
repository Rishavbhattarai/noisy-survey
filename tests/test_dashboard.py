import math
import random

import pytest

from app.db import add_question, record_response
from app.main import randomize
from app.privacy import epsilon_warner, estimate_forced
from app.results import all_results


def _record(conn, q, answers):
    for a in answers:
        record_response(conn, q.id, a)


# --- results module ------------------------------------------------------------


def test_result_without_responses_has_no_estimate(conn):
    add_question(conn, "Q?", "warner", warner_p=0.75)
    (r,) = all_results(conn)
    assert r.estimate is None
    assert r.epsilon == pytest.approx(math.log(3))


def test_result_matches_estimator(conn):
    q = add_question(conn, "Q?", "forced", p_truth=0.5, p_yes=0.3)
    _record(conn, q, [True] * 45 + [False] * 55)
    (r,) = all_results(conn)
    assert r.estimate == estimate_forced(45, 100, 0.5, 0.3)
    assert r.yes_count == 45


# --- GET /api/results -----------------------------------------------------------


def test_api_results_json(conn, make_client):
    f = add_question(conn, "Forced?", "forced", p_truth=0.5, p_yes=0.3)
    w = add_question(conn, "Warner?", "warner", warner_p=0.75)
    _record(conn, f, [True] * 45 + [False] * 55)

    data = make_client().get("/api/results").json()["questions"]
    forced, warner = data

    assert forced["id"] == f.id and forced["scheme"] == "forced"
    assert forced["params"] == pytest.approx({"p_truth": 0.5, "p_yes": 0.3, "p_no": 0.2})
    assert forced["n"] == 100 and forced["yes_count"] == 45
    assert forced["raw_rate"] == pytest.approx(0.45)
    assert forced["pi_hat"] == pytest.approx(0.3)  # (0.45 - 0.3) / 0.5
    assert forced["ci_low"] < forced["pi_hat"] < forced["ci_high"]

    assert warner["id"] == w.id and warner["params"] == {"p": 0.75}
    assert warner["epsilon"] == pytest.approx(epsilon_warner(0.75))
    assert warner["n"] == 0
    assert warner["raw_rate"] is None and warner["pi_hat"] is None and warner["ci_low"] is None


def test_api_reports_unbounded_epsilon_as_null(conn, make_client):
    # p_no = 0: a stored "no" proves the true answer was "no"
    add_question(conn, "Q?", "forced", p_truth=0.7, p_yes=0.3)
    (q,) = make_client().get("/api/results").json()["questions"]
    assert q["epsilon"] is None


def test_end_to_end_estimate_recovers_known_true_rate(conn, make_client):
    # simulate 5,000 respondents, 25% of whom truly answer "yes"
    q = add_question(conn, "Q?", "forced", p_truth=0.5, p_yes=0.3)
    rng = random.Random(123)
    for _ in range(5_000):
        truth = rng.random() < 0.25
        record_response(conn, q.id, randomize(q, truth, rng))

    (r,) = make_client().get("/api/results").json()["questions"]
    assert r["ci_low"] <= 0.25 <= r["ci_high"]
    assert not (r["ci_low"] <= r["raw_rate"] <= r["ci_high"])  # raw is visibly biased


# --- GET /dashboard -----------------------------------------------------------------


def test_dashboard_shows_raw_and_corrected(conn, make_client):
    q = add_question(conn, "Have you ever cheated on an exam?", "forced", p_truth=0.5, p_yes=0.3)
    _record(conn, q, [True] * 45 + [False] * 55)

    html = make_client().get("/dashboard").text
    assert "Have you ever cheated on an exam?" in html
    assert "keep 50% · force yes 30% · force no 20%" in html
    assert "n = 100" in html
    assert "Raw: 45 of 100 stored answers" in html
    assert "Corrected: 30%" in html
    assert "Show as table" in html


def test_dashboard_empty_states(conn, make_client):
    assert "python -m scripts.seed" in make_client().get("/dashboard").text
    add_question(conn, "Q?", "warner", warner_p=0.75)
    html = make_client().get("/dashboard").text
    assert "No responses yet." in html
    assert "keep 75% · flip 25%" in html


def test_dashboard_shows_infinite_epsilon(conn, make_client):
    q = add_question(conn, "Q?", "forced", p_truth=0.7, p_yes=0.3)
    _record(conn, q, [True, False])
    assert "∞ (no guarantee)" in make_client().get("/dashboard").text
