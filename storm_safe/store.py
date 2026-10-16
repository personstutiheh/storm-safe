import threading
from collections import deque
from datetime import datetime, timezone

from storm_safe.guard import initial_state

MAX_LOG = 200

class Store:
    def __init__(self):
        self._lock = threading.Lock()
        self.reset()

    def reset(self):
        with self._lock:
            self._state = initial_state()
            self._log = deque(maxlen=MAX_LOG)
            self._next_id = 1

    def get_state(self):
        with self._lock:
            return dict(self._state)

    def count(self):
        with self._lock:
            return len(self._log)

    def append(self, entry, new_state=None):
        """Add a log entry; optionally replace the satellite state in the same step."""
        with self._lock:
            full = {"id": self._next_id,
                    "time": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    **entry}
            self._next_id += 1
            self._log.append(full)
            if new_state is not None:
                self._state = dict(new_state)
            return full

    def get_log(self, limit=50):
        """Newest first."""
        if limit <= 0:
            return []
        with self._lock:
            items = list(self._log)
        return items[-limit:][::-1]