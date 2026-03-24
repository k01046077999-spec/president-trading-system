from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Dict, Optional


class CacheStore:
    def __init__(self, path: str = "data/cache.json") -> None:
        self.path = Path(path)
        self.lock = Lock()
        self.data: Dict[str, Any] = {"main": None, "sub": None}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            try:
                self.data = json.loads(self.path.read_text(encoding="utf-8"))
            except Exception:
                self.data = {"main": None, "sub": None}

    def get(self, mode: str) -> Optional[Dict[str, Any]]:
        with self.lock:
            return self.data.get(mode)

    def set(self, mode: str, snapshot: Dict[str, Any]) -> None:
        with self.lock:
            self.data[mode] = snapshot
            self.path.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")

    @staticmethod
    def now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()
