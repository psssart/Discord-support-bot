import os
import sqlite3
from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI()

DB_PATH = os.getenv("DB_PATH", "/opt/cronbot/run/cronbot.sqlite")

@app.get("/healthz")
def healthz():
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' LIMIT 1;")
        _ = cur.fetchone()
        conn.close()
        db_ok = True
    except Exception as e:
        db_ok = False

    status = "ok" if db_ok else "degraded"
    return JSONResponse({"status": status, "db": db_ok})
