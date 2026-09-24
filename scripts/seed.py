"""Create the database and add sample sensitive questions.

Run from the project root:  python -m scripts.seed
Safe to run twice: questions are only added to an empty database.
"""

import sqlite3

from app.db import DEFAULT_DB_PATH, add_question, connect, init_db, list_questions

SAMPLE_QUESTIONS = [
    # forced: 50% truthful, 30% forced "yes", 20% forced "no"
    dict(text="Have you ever cheated on an exam?", scheme="forced", p_truth=0.5, p_yes=0.3),
    # warner: 75% truthful, 25% flipped
    dict(text="Have you used a recreational drug in the past year?", scheme="warner", warner_p=0.75),
    # forced: 60% truthful, 20% forced "yes", 20% forced "no"
    dict(text="Have you ever lied on your CV?", scheme="forced", p_truth=0.6, p_yes=0.2),
]


def seed(conn: sqlite3.Connection) -> int:
    """Add the sample questions if there are none yet. Returns how many were added."""
    init_db(conn)
    if list_questions(conn):
        return 0
    for q in SAMPLE_QUESTIONS:
        add_question(conn, **q)
    return len(SAMPLE_QUESTIONS)


if __name__ == "__main__":
    with connect() as conn:
        added = seed(conn)
    print(f"Seeded {added} question(s) into {DEFAULT_DB_PATH}")
