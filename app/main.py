import math
import random
import sqlite3
from collections.abc import Iterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app.db import DEFAULT_DB_PATH, Question, connect, init_db, list_questions, record_response
from app.privacy import randomize_forced, randomize_warner
from app.results import all_results

TEMPLATES = Jinja2Templates(directory=Path(__file__).parent / "templates")
TEMPLATES.env.filters["pct"] = lambda x: f"{x * 100:.0f}%"
TEMPLATES.env.globals["inf"] = math.inf
TEMPLATES.env.filters["pos"] = lambda x: f"{x * 100:.2f}%"  # CSS position along a 0-100% axis
ANSWERS = {"yes": True, "no": False}


@asynccontextmanager
async def lifespan(app: FastAPI):
    with connect(DEFAULT_DB_PATH) as conn:
        init_db(conn)
    yield


app = FastAPI(title="Noisy Survey", lifespan=lifespan)


def get_db() -> Iterator[sqlite3.Connection]:
    conn = connect(DEFAULT_DB_PATH)
    try:
        yield conn
    finally:
        conn.close()


def get_rng() -> random.Random:
    # OS-level randomness: a respondent's noise must not be predictable
    return random.SystemRandom()


def randomize(question: Question, true_answer: bool, rng: random.Random) -> bool:
    if question.scheme == "forced":
        return randomize_forced(true_answer, question.p_truth, question.p_yes, rng)
    return randomize_warner(true_answer, question.warner_p, rng)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/")
def index():
    return RedirectResponse("/survey")


@app.get("/survey")
def survey_form(request: Request, conn: sqlite3.Connection = Depends(get_db)):
    return TEMPLATES.TemplateResponse(request, "survey.html", {"questions": list_questions(conn)})


@app.post("/survey")
async def submit_survey(
    request: Request,
    conn: sqlite3.Connection = Depends(get_db),
    rng: random.Random = Depends(get_rng),
):
    form = await request.form()

    # validate everything first, so a bad field stores nothing at all
    answers: list[tuple[Question, bool]] = []
    for q in list_questions(conn):
        value = form.get(f"q_{q.id}")
        if value is None:
            continue  # skipped questions are allowed and store nothing
        if value not in ANSWERS:
            raise HTTPException(status_code=422, detail="answer must be 'yes' or 'no'")
        answers.append((q, ANSWERS[value]))

    # The true answer only lives in this request's memory: it is randomized
    # here and only the noisy result is stored. Nothing is logged.
    for q, true_answer in answers:
        record_response(conn, q.id, randomize(q, true_answer, rng))

    return RedirectResponse("/thanks", status_code=303)


@app.get("/thanks")
def thanks(request: Request):
    return TEMPLATES.TemplateResponse(request, "thanks.html")


@app.get("/api/results")
def api_results(conn: sqlite3.Connection = Depends(get_db)):
    return {"questions": [r.to_dict() for r in all_results(conn)]}


@app.get("/dashboard")
def dashboard(request: Request, conn: sqlite3.Connection = Depends(get_db)):
    return TEMPLATES.TemplateResponse(request, "dashboard.html", {"results": all_results(conn)})
