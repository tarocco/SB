from contextlib import contextmanager
import queue


def spin(cycles):
    while cycles > 0:
        cycles -= 1


def flush_queue(q):
    try:
        while True:
            q.get_nowait()
    except queue.Empty:
        pass


@contextmanager
def acquire_timeout(lock, timeout):
    result = lock.acquire(timeout=timeout)
    yield result
    if result:
        lock.release()
