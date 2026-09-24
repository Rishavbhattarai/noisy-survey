from app.db import add_question, count_responses
from tests.conftest import FixedRng


def _all_responses(conn):
    return conn.execute("SELECT question_id, reported_answer FROM responses ORDER BY id").fetchall()


# --- GET /survey ---------------------------------------------------------------


def test_survey_page_lists_questions_with_protection_note(conn, make_client):
    add_question(conn, "Have you ever cheated on an exam?", "forced", p_truth=0.5, p_yes=0.3)
    add_question(conn, "Have you used a drug?", "warner", warner_p=0.75)

    html = make_client().get("/survey").text
    assert "Have you ever cheated on an exam?" in html
    assert "Have you used a drug?" in html
    assert "50% of the time" in html and "(30%)" in html and "(20%)" in html
    assert "75% of the time" in html and "other 25%" in html


def test_empty_survey_explains_how_to_seed(make_client):
    assert "python -m scripts.seed" in make_client().get("/survey").text


# --- POST /survey ---------------------------------------------------------------


def test_submit_stores_one_noisy_row_per_answer_and_redirects(conn, make_client):
    a = add_question(conn, "A?", "forced", p_truth=0.5, p_yes=0.3)
    b = add_question(conn, "B?", "warner", warner_p=0.75)

    response = make_client().post(
        "/survey", data={f"q_{a.id}": "yes", f"q_{b.id}": "no"}, follow_redirects=False
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/thanks"
    rows = _all_responses(conn)
    assert [r["question_id"] for r in rows] == [a.id, b.id]
    assert all(r["reported_answer"] in (0, 1) for r in rows)


def test_true_answer_is_randomized_before_storage(conn, make_client):
    # rng draw 0.99 falls in the forced-"no" band (>= p_truth + p_yes = 0.8),
    # so a true "yes" must be stored as "no"
    q = add_question(conn, "Q?", "forced", p_truth=0.5, p_yes=0.3)
    make_client(FixedRng(0.99)).post("/survey", data={f"q_{q.id}": "yes"})
    assert count_responses(conn, q.id) == (0, 1)


def test_warner_flip_is_applied(conn, make_client):
    # rng draw 0.9 >= p = 0.75, so the answer is flipped: true "no" is stored as "yes"
    q = add_question(conn, "Q?", "warner", warner_p=0.75)
    make_client(FixedRng(0.9)).post("/survey", data={f"q_{q.id}": "no"})
    assert count_responses(conn, q.id) == (1, 1)


def test_truthful_draw_keeps_answer(conn, make_client):
    q = add_question(conn, "Q?", "forced", p_truth=0.5, p_yes=0.3)
    make_client(FixedRng(0.1)).post("/survey", data={f"q_{q.id}": "no"})
    assert count_responses(conn, q.id) == (0, 1)


def test_skipped_questions_store_nothing(conn, make_client):
    a = add_question(conn, "A?", "warner", warner_p=0.75)
    b = add_question(conn, "B?", "warner", warner_p=0.75)
    make_client().post("/survey", data={f"q_{a.id}": "yes"})
    assert count_responses(conn, a.id)[1] == 1
    assert count_responses(conn, b.id) == (0, 0)


def test_invalid_answer_is_rejected_and_nothing_is_stored(conn, make_client):
    a = add_question(conn, "A?", "warner", warner_p=0.75)
    b = add_question(conn, "B?", "warner", warner_p=0.75)
    response = make_client().post("/survey", data={f"q_{a.id}": "yes", f"q_{b.id}": "maybe"})
    assert response.status_code == 422
    assert _all_responses(conn) == []


def test_unknown_question_fields_are_ignored(conn, make_client):
    q = add_question(conn, "Q?", "warner", warner_p=0.75)
    make_client().post("/survey", data={f"q_{q.id}": "yes", "q_999": "yes", "name": "Alice"})
    assert [r["question_id"] for r in _all_responses(conn)] == [q.id]


def test_thanks_page(make_client):
    response = make_client().get("/thanks")
    assert response.status_code == 200
    assert "Thank you" in response.text
