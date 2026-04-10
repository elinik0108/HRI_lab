from HRI_lab_Pepper.tablet.service import TabletService
from HRI_lab_Pepper.tablet.deploy import (
    deploy_tablet_pages,
    sftp_makedirs,
    TABLET_ROBOT_BASE,
    TABLET_REMOTE_DIR,
)

__all__ = [
    "TabletService",
    "deploy_tablet_pages",
    "sftp_makedirs",
    "TABLET_ROBOT_BASE",
    "TABLET_REMOTE_DIR",
]
