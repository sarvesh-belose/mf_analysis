import threading

# Global stop events for long-running tasks
# Key: task_name (e.g., "fetch_navs"), Value: threading.Event()
STOP_EVENTS = {
    "fetch_navs": threading.Event(),
    "compute_metrics": threading.Event(),
    "load_master": threading.Event(),
    "load_tri": threading.Event(),
}

def signal_stop(task_name: str):
    if task_name in STOP_EVENTS:
        STOP_EVENTS[task_name].set()

def should_stop(task_name: str) -> bool:
    if task_name in STOP_EVENTS:
        return STOP_EVENTS[task_name].is_set()
    return False

def reset_signal(task_name: str):
    if task_name in STOP_EVENTS:
        STOP_EVENTS[task_name].clear()
