"""Fill the database with synthetic respondents whose true answers you know.

Every simulated answer goes through the same randomization as a real one, so
the dashboard shows how close the corrected estimate gets to the truth.

Run from the project root:
    python -m scripts.simulate --n 1000 --true-rate 0.25
    python -m scripts.simulate --n 500 --true-rate 0.1 --question 2 --seed 7
    python -m scripts.simulate --reset --n 2000
"""

import argparse
import random
import sqlite3

from app.db import connect, count_responses, get_question, list_questions, record_response
from app.main import randomize
from app.results import question_result
from scripts.seed import seed


def simulate(
    conn: sqlite3.Connection,
    n: int,
    true_rate: float,
    question_ids: list[int] | None = None,
    rng: random.Random | None = None,
) -> None:
    if n <= 0:
        raise ValueError("n must be > 0")
    if not 0.0 <= true_rate <= 1.0:
        raise ValueError("true_rate must be in [0, 1]")
    rng = rng or random.Random()

    if question_ids:
        questions = [get_question(conn, qid) for qid in question_ids]
        if None in questions:
            raise ValueError(f"unknown question id in {question_ids}")
    else:
        questions = list_questions(conn)

    for q in questions:
        for _ in range(n):
            truth = rng.random() < true_rate
            record_response(conn, q.id, randomize(q, truth, rng))


def reset_responses(conn: sqlite3.Connection) -> None:
    conn.execute("DELETE FROM responses")
    conn.commit()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--n", type=int, default=1000, help="respondents per question (default 1000)")
    parser.add_argument("--true-rate", type=float, default=0.25, help="true share of 'yes' (default 0.25)")
    parser.add_argument("--question", type=int, action="append", help="only this question id (repeatable)")
    parser.add_argument("--seed", type=int, help="random seed for a reproducible run")
    parser.add_argument("--reset", action="store_true", help="delete all stored responses first")
    args = parser.parse_args()

    with connect() as conn:
        seed(conn)
        if args.reset:
            reset_responses(conn)
        simulate(conn, args.n, args.true_rate, args.question, random.Random(args.seed))

        print(f"Simulated {args.n} respondents per question, true rate {args.true_rate:.0%}\n")
        print(f"{'id':>3}  {'n':>6}  {'raw':>6}  {'corrected':>9}  {'95% CI':>13}  question")
        for q in list_questions(conn):
            if count_responses(conn, q.id)[1] == 0:
                continue
            est = question_result(conn, q).estimate
            ci = f"{est.ci_low:.0%}–{est.ci_high:.0%}"
            print(f"{q.id:>3}  {est.n:>6}  {est.raw_rate:>6.1%}  {est.pi_hat:>9.1%}  {ci:>13}  {q.text}")
    print("\nTotals include any earlier responses. Use --reset for a clean run.")


if __name__ == "__main__":
    main()
