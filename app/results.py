"""Turn stored noisy answers into raw vs corrected results per question."""

import math
import sqlite3
from dataclasses import dataclass

from app.db import Question, count_responses, list_questions
from app.privacy import (
    Estimate,
    epsilon_forced,
    epsilon_warner,
    estimate_forced,
    estimate_warner,
)


@dataclass(frozen=True)
class QuestionResult:
    question: Question
    yes_count: int
    epsilon: float  # math.inf when there is no privacy guarantee
    estimate: Estimate | None  # None until the question has responses

    @property
    def params(self) -> dict[str, float]:
        q = self.question
        if q.scheme == "forced":
            return {"p_truth": q.p_truth, "p_yes": q.p_yes, "p_no": q.p_no}
        return {"p": q.warner_p}

    @property
    def mechanism(self) -> str:
        """Human-readable description of the noise, e.g. 'keep 50% · force yes 30% · force no 20%'."""
        q = self.question
        if q.scheme == "forced":
            return f"keep {q.p_truth:.0%} · force yes {q.p_yes:.0%} · force no {q.p_no:.0%}"
        return f"keep {q.warner_p:.0%} · flip {1 - q.warner_p:.0%}"

    def to_dict(self) -> dict:
        est = self.estimate
        return {
            "id": self.question.id,
            "text": self.question.text,
            "scheme": self.question.scheme,
            "params": self.params,
            # JSON has no infinity: null means "no privacy guarantee"
            "epsilon": None if math.isinf(self.epsilon) else self.epsilon,
            "n": est.n if est else 0,
            "yes_count": self.yes_count,
            "raw_rate": est.raw_rate if est else None,
            "pi_hat": est.pi_hat if est else None,
            "se": est.se if est else None,
            "ci_low": est.ci_low if est else None,
            "ci_high": est.ci_high if est else None,
        }


def question_result(conn: sqlite3.Connection, q: Question) -> QuestionResult:
    yes, n = count_responses(conn, q.id)
    if q.scheme == "forced":
        eps = epsilon_forced(q.p_truth, q.p_yes)
        est = estimate_forced(yes, n, q.p_truth, q.p_yes) if n else None
    else:
        eps = epsilon_warner(q.warner_p)
        est = estimate_warner(yes, n, q.warner_p) if n else None
    return QuestionResult(question=q, yes_count=yes, epsilon=eps, estimate=est)


def all_results(conn: sqlite3.Connection) -> list[QuestionResult]:
    return [question_result(conn, q) for q in list_questions(conn)]
