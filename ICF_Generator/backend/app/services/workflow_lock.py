"""Serialize revision, template, review and export operations within this process."""
from collections import defaultdict
from threading import RLock

_locks = defaultdict(RLock)
_guard = RLock()


def study_lock(study_id):
    with _guard:
        return _locks[study_id.strip()]
