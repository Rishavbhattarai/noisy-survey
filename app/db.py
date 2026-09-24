"""SQLite storage.

Privacy by design: the ``responses`` table holds only the *randomized*
answer and the question it belongs to. There is deliberately no timestamp,
IP address, user agent, session or respondent id, so a stored row cannot be
linked back to a person. The true answer never reaches this module.
"""

import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from app.privacy import validate_forced, validate_warner

DEFAULT_DB_PATH = Path(os.environ.get("NOISY_SURVEY_DB", "survey.db"))

SCHEMES = ("forced", "warner")

SCHEMA = """
CREATE TABLE IF NOT EXISTS questions (
    id       INTEGER PRIMARY KEY,
    text     TEXT NOT NULL,
    scheme   TEXT NOT NULL CHECK (scheme IN ('forced', 'warner')),
    p_truth  REAL,  -- forced: probability the true answer is kept
    p_yes    REAL,  -- forced: probability "yes" is forced (p_no = 1 - p_truth - p_yes)
    warner_p REAL,  -- warner: probability the true answer is kept, else flipped
    CHECK (
        (scheme = 'forced' AND p_truth IS NOT NULL AND p_yes IS NOT NULL AND warner_p IS NULL)
        OR (scheme = 'warner' AND warner_p IS NOT NULL AND p_truth IS NULL AND p_yes IS NULL)
    )
);

CREATE TABLE IF NOT EXISTS responses (
    id              INTEGER PRIMARY KEY,
    question_id     INTEGER NOT NULL REFERENCES questions (id),
    reported_answer INTEGER NOT NULL CHECK (reported_answer IN (0, 1))
);
"""


@dataclass(frozen=True)
class Question:
    id: int
    text: str
    scheme: str
    p_truth: float | None = None
    p_yes: float | None = None
    warner_p: float | None = None

    @property
    def p_no(self) -> float | None:
        if self.scheme != "forced":
            return None
        return validate_forced(self.p_truth, self.p_yes)


def connect(path: str | Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()


def add_question(
    conn: sqlite3.Connection,
    text: str,
    scheme: str,
    *,
    p_truth: float | None = None,
    p_yes: float | None = None,
    warner_p: float | None = None,
) -> Question:
    if scheme == "forced":
        if p_truth is None or p_yes is None or warner_p is not None:
            raise ValueError("forced scheme needs p_truth and p_yes (and no warner_p)")
        validate_forced(p_truth, p_yes)
    elif scheme == "warner":
        if warner_p is None or p_truth is not None or p_yes is not None:
            raise ValueError("warner scheme needs warner_p (and no p_truth/p_yes)")
        validate_warner(warner_p)
    else:
        raise ValueError(f"scheme must be one of {SCHEMES}, got {scheme!r}")

    cur = conn.execute(
        "INSERT INTO questions (text, scheme, p_truth, p_yes, warner_p) VALUES (?, ?, ?, ?, ?)",
        (text, scheme, p_truth, p_yes, warner_p),
    )
    conn.commit()
    return get_question(conn, cur.lastrowid)


def _to_question(row: sqlite3.Row) -> Question:
    return Question(**dict(row))


def get_question(conn: sqlite3.Connection, question_id: int) -> Question | None:
    row = conn.execute("SELECT * FROM questions WHERE id = ?", (question_id,)).fetchone()
    return _to_question(row) if row else None


def list_questions(conn: sqlite3.Connection) -> list[Question]:
    rows = conn.execute("SELECT * FROM questions ORDER BY id").fetchall()
    return [_to_question(r) for r in rows]


def record_response(conn: sqlite3.Connection, question_id: int, reported_answer: bool) -> None:
    """Store an already-randomized answer. Never pass the true answer here."""
    conn.execute(
        "INSERT INTO responses (question_id, reported_answer) VALUES (?, ?)",
        (question_id, int(reported_answer)),
    )
    conn.commit()


def count_responses(conn: sqlite3.Connection, question_id: int) -> tuple[int, int]:
    """Return ``(yes_count, n)`` of stored (noisy) answers for a question."""
    yes, n = conn.execute(
        "SELECT COALESCE(SUM(reported_answer), 0), COUNT(*) FROM responses WHERE question_id = ?",
        (question_id,),
    ).fetchone()
    return yes, n
