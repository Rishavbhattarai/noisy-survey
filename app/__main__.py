"""Run the app with privacy-safe server settings:  python -m app

Uvicorn's access log records each visitor's IP address and the time of every
request. Matched against the order rows are stored in, that could link noisy
answers back to a person, so it is switched off here.
"""

import os

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=os.environ.get("HOST", "127.0.0.1"),
        port=int(os.environ.get("PORT", "8000")),
        access_log=False,
        reload=os.environ.get("RELOAD") == "1",
    )
