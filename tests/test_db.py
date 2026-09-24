import sqlite3

import pytest

from app.db import (
    add_question,
    connect,
    count_responses,
    get_question,
    init_db,
    list_questions,
    record_response,
)
from scripts.seed import SAMPLE_QUESTIONS, seed


@pytest.fixture
def conn(tmp_path):
    c = connect(tmp_path / "test.db")
    init_db(c)
    yield c
    c.close()


def _columns(conn, table):
    return {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}


# --- privacy: the schema stores nothing that could identify a respondent ----


def test_responses_table_has_no_identifying_columns(conn):
    # If someone adds created_at, ip, session_id, ... this test should fail loudly.
    assert _columns(conn, "responses") == {"id", "question_id", "reported_answer"}


# --- questions ---------------------------------------------------------------


def test_add_and_get_forced_question(conn):
    q = add_question(conn, "Q?", "forced", p_truth=0.5, p_yes=0.3)
    assert get_question(conn, q.id) == q
    assert q.scheme == "forced" and q.warner_p is None
    assert q.p_no == pytest.approx(0.2)


def test_add_warner_question(conn):
    q = add_question(conn, "Q?", "warner", warner_p=0.75)
    assert q.warner_p == 0.75 and q.p_truth is None and q.p_no is None


def test_list_questions_in_insert_order(conn):
    a = add_question(conn, "A?", "forced", p_truth=0.5, p_yes=0.3)
    b = add_question(conn, "B?", "warner", warner_p=0.8)
    assert list_questions(conn) == [a, b]


def test_get_missing_question_returns_none(conn):
    assert get_question(conn, 999) is None


@pytest.mark.parametrize(
    "kwargs",
    [
        dict(scheme="unknown", p_truth=0.5, p_yes=0.3),
        dict(scheme="forced", warner_p=0.75),  # wrong params for scheme
        dict(scheme="warner", p_truth=0.5, p_yes=0.3),  # wrong params for scheme
        dict(scheme="forced", p_truth=0.5, p_yes=0.3, warner_p=0.7),  # mixed params
        dict(scheme="forced", p_truth=0.8, p_yes=0.3),  # probabilities > 1
        dict(scheme="warner", warner_p=0.5),  # no signal
    ],
)
def test_invalid_questions_are_rejected(conn, kwargs):
    with pytest.raises(ValueError):
        add_question(conn, "Q?", **kwargs)
    assert list_questions(conn) == []


def test_schema_check_blocks_bad_rows_written_directly(conn):
    # defence in depth: even raw SQL can't store a forced question without its params
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO questions (text, scheme) VALUES ('Q?', 'forced')")


# --- responses ---------------------------------------------------------------


def test_record_and_count_responses(conn):
    q = add_question(conn, "Q?", "warner", warner_p=0.75)
    for answer in [True, True, False, True, False]:
        record_response(conn, q.id, answer)
    assert count_responses(conn, q.id) == (3, 5)


def test_counts_are_per_question(conn):
    a = add_question(conn, "A?", "warner", warner_p=0.75)
    b = add_question(conn, "B?", "warner", warner_p=0.75)
    record_response(conn, a.id, True)
    assert count_responses(conn, b.id) == (0, 0)


def test_response_for_unknown_question_is_rejected(conn):
    with pytest.raises(sqlite3.IntegrityError):
        record_response(conn, 999, True)


def test_reported_answer_must_be_boolean(conn):
    q = add_question(conn, "Q?", "warner", warner_p=0.75)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO responses (question_id, reported_answer) VALUES (?, 2)", (q.id,))


# --- seed script -------------------------------------------------------------


def test_seed_adds_sample_questions_once(tmp_path):
    c = connect(tmp_path / "seed.db")
    assert seed(c) == len(SAMPLE_QUESTIONS)
    assert seed(c) == 0  # idempotent
    questions = list_questions(c)
    assert len(questions) == len(SAMPLE_QUESTIONS)
    assert {q.scheme for q in questions} == {"forced", "warner"}
    c.close()
