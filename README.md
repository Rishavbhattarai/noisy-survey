# Noisy Survey

An anonymous survey app with built-in noise, based on the idea behind *Safely Report*.

Sensitive yes/no answers are randomized **before** they are stored. For example, "yes" is recorded 30% of the time no matter what the person said. No stored answer can be traced back to anyone, yet the true percentage can still be recovered from the known noise rate. A dashboard shows the raw (noisy) results next to the corrected estimate.

## Run

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
pytest -q
```
