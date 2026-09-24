from fastapi import FastAPI

app = FastAPI(title="Noisy Survey")


@app.get("/")
def health():
    return {"status": "ok"}
