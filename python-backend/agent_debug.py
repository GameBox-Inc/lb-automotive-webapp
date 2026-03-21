# region agent log
"""Session-scoped NDJSON debug logging (debug mode). Do not log secrets."""
import json
import time
from pathlib import Path

_SESSION = "73bbc4"


def _log_path() -> Path:
    base = Path(__file__).resolve().parent
    if base.name == "python-backend":
        return base.parent / "debug-73bbc4.log"
    return base / "debug-73bbc4.log"


def agent_debug_log(hypothesis_id: str, location: str, message: str, data=None):
    payload = {
        "sessionId": _SESSION,
        "hypothesisId": hypothesis_id,
        "location": location,
        "message": message,
        "data": data or {},
        "timestamp": int(time.time() * 1000),
    }
    line = json.dumps(payload, default=str) + "\n"
    try:
        with open(_log_path(), "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass
    print(f"[AGENT_DEBUG_{_SESSION}] {line.strip()}", flush=True)


# endregion
