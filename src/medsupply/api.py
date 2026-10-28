import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from .pipeline import Database, database_url, summary
from .retrieval import ask


def create_app(root=None):
    root = Path(root or os.environ.get("MEDSUPPLY_ROOT", ".")).resolve()
    app = FastAPI(title="MedSupply Monitor", version="1.0.0")

    def db():
        return Database(database_url(root))

    @app.get("/", include_in_schema=False)
    def home():
        return FileResponse(Path(__file__).parent / "static/index.html")

    @app.get("/health")
    def health():
        conn = db()
        try:
            state = summary(conn)
            return {"status": "ok", "has_data": bool(state['latest_snapshot'])}
        finally:
            conn.close()

    @app.get("/api/summary")
    def get_summary():
        conn = db()
        try:
            return summary(conn)
        finally:
            conn.close()

    @app.get("/api/observations")
    def observations(q: str = Query("", max_length=150), critical: bool = False,
                     limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0)):
        conn = db()
        try:
            # Literal substring search; escape wildcard characters supplied by the user.
            pattern = "%" + q.replace("!", "!!").replace("%", "!%").replace("_", "!_").lower() + "%"
            where = "(LOWER(product) LIKE ? ESCAPE '!' OR LOWER(ingredient) LIKE ? ESCAPE '!')"
            params = [pattern, pattern]
            if critical:
                where += " AND critical_flag=1"
            total = conn.rows("SELECT COUNT(*) AS n FROM current_observations WHERE " + where, params)[0]['n']
            rows = conn.rows("SELECT * FROM current_observations WHERE " + where +
                             " ORDER BY source_updated DESC,product_key LIMIT ? OFFSET ?", [*params, limit, offset])
            return {"total": total, "items": rows, "limit": limit, "offset": offset}
        finally:
            conn.close()

    @app.get("/api/changes")
    def changes():
        conn = db()
        try:
            return {"snapshot_count": summary(conn)['snapshot_count'], "items": conn.rows(
                "SELECT c.* FROM changes c JOIN snapshots s ON s.snapshot_id=c.snapshot_id "
                "WHERE s.observed_at=(SELECT MAX(observed_at) FROM snapshots) ORDER BY c.product_key,c.field")}
        finally:
            conn.close()

    @app.get("/api/quality")
    def quality():
        conn = db()
        try:
            return {"runs": conn.rows("SELECT * FROM runs ORDER BY observed_at DESC LIMIT 30"),
                    "quarantine": conn.rows("SELECT run_id,row_number,issue FROM quarantine ORDER BY run_id,row_number")}
        finally:
            conn.close()

    class Question(BaseModel):
        question: str = Field(min_length=3, max_length=1000)
        product_key: str | None = Field(default=None, max_length=30)
        use_llm: bool = False

    @app.post("/api/ask")
    def question(body: Question):
        if body.use_llm and os.environ.get("ENABLE_LIVE_LLM") != "true":
            raise HTTPException(403, "Live generation is disabled; use the extractive evidence mode")
        conn = db()
        try:
            return ask(root, conn, body.question, body.product_key, body.use_llm)
        except (ValueError, OSError, KeyError) as exc:
            raise HTTPException(502, "Evidence generation failed; use extractive mode or check provider configuration") from exc
        finally:
            conn.close()

    return app


app = create_app()
