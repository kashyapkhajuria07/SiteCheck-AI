"""In-memory + JSON file session persistence for inspection results."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from schemas.inspection import InspectionSession

_sessions: dict[str, InspectionSession] = {}


def save_session(session: InspectionSession, outputs_dir: Path) -> None:
    _sessions[session.session_id] = session
    session_dir = outputs_dir / session.session_id
    session_dir.mkdir(parents=True, exist_ok=True)
    meta_path = session_dir / "session.json"
    meta_path.write_text(session.model_dump_json(indent=2), encoding="utf-8")


def get_session(session_id: str, outputs_dir: Path) -> Optional[InspectionSession]:
    if session_id in _sessions:
        return _sessions[session_id]

    meta_path = outputs_dir / session_id / "session.json"
    if not meta_path.exists():
        return None

    data = json.loads(meta_path.read_text(encoding="utf-8"))
    session = InspectionSession.model_validate(data)
    _sessions[session_id] = session
    return session
