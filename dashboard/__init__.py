"""
HRI_lab_Pepper dashboard module.

Run with:
    python -m HRI_lab_Pepper.dashboard --url tcp://ROBOT_IP:9559

Or import for programmatic use:
    from HRI_lab_Pepper.dashboard import run
    run(url="tcp://172.18.48.50:9559", port=8080)
"""

from HRI_lab_Pepper.dashboard.server import run, app, get_tablet_input

__all__ = ["run", "app", "get_tablet_input"]
