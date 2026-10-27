"""Process-local capture activity; optional work never competes with a running HUD."""
import threading
import weakref

_lock=threading.Lock()
_engines=weakref.WeakSet()


def register(engine):
    with _lock:_engines.add(engine)


def busy():
    with _lock:return any(not engine.stop.is_set() and engine.thread.is_alive() for engine in _engines)
