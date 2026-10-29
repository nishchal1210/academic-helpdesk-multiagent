import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3


class AuditLog:
    def __init__(self, state_dir: Path):
        state_dir.mkdir(parents=True, exist_ok=True)
        self.path = state_dir / "helpdesk.sqlite3"
        with sqlite3.connect(self.path) as db:
            db.execute("""CREATE TABLE IF NOT EXISTS requests (
                id TEXT PRIMARY KEY, timestamp TEXT, question TEXT, status TEXT,
                reason TEXT, route TEXT, mode TEXT, model TEXT, sources TEXT, elapsed REAL)""")

    def record(self, question, answer):
        with sqlite3.connect(self.path) as db:
            db.execute("INSERT INTO requests VALUES (?,?,?,?,?,?,?,?,?,?)", (
                answer.question_id, datetime.now(timezone.utc).isoformat(), question, answer.status,
                answer.reason, answer.route, answer.mode, answer.model,
                json.dumps([s.document_id for s in answer.sources]), answer.elapsed_seconds))

    def export_unanswered(self, path: Path):
        with sqlite3.connect(self.path) as db:
            rows = db.execute("SELECT * FROM requests WHERE status != 'answered' ORDER BY timestamp")
            names = [col[0] for col in rows.description]
            with path.open("w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(names)
                writer.writerows(rows)
