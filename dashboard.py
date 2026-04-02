#!/usr/bin/env python
# =============================================================================
#   HRI_lab_Pepper — Dashboard (legacy entry point)
#   The dashboard has moved to HRI_lab_Pepper/dashboard/
#   Prefer:  python -m HRI_lab_Pepper.dashboard --url tcp://ROBOT_IP:9559
# =============================================================================
"""
Legacy entry point — kept for backwards compatibility.
The dashboard has moved to ``HRI_lab_Pepper/dashboard/``.

Prefer the module form::

    python -m HRI_lab_Pepper.dashboard --url tcp://ROBOT_IP:9559

Or import programmatically::

    from HRI_lab_Pepper.dashboard import run
    run(url="tcp://ROBOT_IP:9559", port=8080)
"""

import os
import sys

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from HRI_lab_Pepper.dashboard.server import _cli  # noqa: E402

if __name__ == "__main__":
    _cli()

