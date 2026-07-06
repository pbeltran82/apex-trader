import threading
import time
from datetime import datetime

from backend.exit_manager import run_exit_manager


_running = False
_thread = None

CHECK_INTERVAL = 5


def monitor_loop():
    global _running

    print("===================================================")
    print("Kyle Position Monitor Started")
    print("===================================================")

    while _running:

        try:
            result = run_exit_manager()

            if result["checked"] > 0:
                print(
                    f"[{datetime.utcnow().isoformat()}] "
                    f"Checked {result['checked']} position(s)"
                )

        except Exception as e:
            print(f"Position Monitor Error: {e}")

        time.sleep(CHECK_INTERVAL)

    print("Kyle Position Monitor Stopped")


def start_position_monitor():

    global _running
    global _thread

    if _running:
        return

    _running = True

    _thread = threading.Thread(
        target=monitor_loop,
        daemon=True,
    )

    _thread.start()


def stop_position_monitor():

    global _running

    _running = False


def monitor_status():

    return {
        "running": _running,
        "interval_seconds": CHECK_INTERVAL,
        "thread_alive": _thread.is_alive() if _thread else False,
    }