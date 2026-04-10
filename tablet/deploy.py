"""
HRI_lab_Pepper — Tablet page deployment via SSH/SFTP
=====================================================

Deploys compiled tablet HTML pages to the robot's built-in web server so the
tablet loads them over the **internal** robot↔tablet WiFi bridge (fixed IP
198.18.0.1) instead of fetching them from the laptop over external WiFi.

Usage::

    from HRI_lab_Pepper.tablet import deploy_tablet_pages

    on_robot = deploy_tablet_pages(
        robot_ip=  "172.18.48.50",
        dash_url=  "http://192.168.1.10:8080",
        src_dir=   Path("dashboard/static/tablet"),
    )

The function is intentionally side-effect-free beyond SFTP file writes so both
the dashboard server and standalone demo scripts can call it without coupling.
"""

import io
from pathlib import Path

# Robot's fixed internal IP — only reachable by the tablet over the dedicated
# WiFi bridge.  Pages served from here never cross external WiFi.
TABLET_ROBOT_BASE = "http://198.18.0.1/apps/tablet"

# Remote path on the robot where the built-in HTTP server looks for pages.
TABLET_REMOTE_DIR = ".local/share/PackageManager/apps/tablet/html"


def sftp_makedirs(sftp, remote_path: str) -> None:
    """Recursively create directories on the SFTP server (like ``mkdir -p``)."""
    parts = remote_path.replace("\\", "/").split("/")
    path  = ""
    for part in parts:
        if not part:
            continue
        path = f"{path}/{part}" if path else part
        try:
            sftp.stat(path)
        except FileNotFoundError:
            try:
                sftp.mkdir(path)
            except OSError:
                pass  # concurrent creation or already exists


def deploy_tablet_pages(robot_ip: str, dash_url: str, src_dir: Path) -> bool:
    """
    Copy tablet HTML pages from *src_dir* to the robot at::

        ~/.local/share/PackageManager/apps/tablet/html/

    The robot's built-in web server then serves them at::

        http://198.18.0.1/apps/tablet/<page>

    If *src_dir* contains a ``dist/`` sub-directory it will be preferred (ES5,
    compatible with the robot's old Chromium browser).

    Every ``*.html`` file has its ``fetch("/api/tablet_input"`` callback URL
    patched to the absolute ``<dash_url>/api/tablet_input`` so the tablet can
    still reach the laptop dashboard server across the LAN.

    SSH authentication is tried in order:
        1. keyboard-interactive (``nao`` / ``nao``)
        2. plain password (``nao`` / ``robofun``)
        3. public key (``~/.ssh/id_ed25519``, ``id_rsa``, ``id_ecdsa``)

    Returns ``True`` on success, ``False`` on any failure (paramiko missing,
    SSH error, SFTP error).
    """
    try:
        import paramiko  # noqa: PLC0415
    except ImportError:
        print("[TABLET] paramiko not installed — pages will be served from the laptop.")
        print("[TABLET]   Install with:  pip install paramiko")
        return False

    dist_dir   = src_dir / "dist"
    deploy_dir = dist_dir if dist_dir.is_dir() else src_dir
    if not deploy_dir.is_dir():
        print(f"[TABLET] Tablet pages not found at {deploy_dir} — skipping deploy.")
        return False

    if deploy_dir == dist_dir:
        print("[TABLET] Deploying compiled dist/ pages (ES5).")
    else:
        print("[TABLET] WARN: dist/ not found — deploying uncompiled source pages.")
        print("[TABLET]   Run `node build.js` in dashboard/static/tablet/ for robot compatibility.")

    transport = None
    sftp      = None
    try:
        transport = paramiko.Transport((robot_ip, 22))
        transport.connect()

        def _ki_handler(title, instructions, prompt_list):
            return ["nao" for _ in prompt_list]

        authenticated = False

        # ── Method 1: keyboard-interactive ──────────────────────────────────
        try:
            transport.auth_interactive("nao", _ki_handler)
            authenticated = True
        except paramiko.AuthenticationException:
            pass

        # ── Method 2: plain password ─────────────────────────────────────────
        if not authenticated:
            try:
                transport.auth_password("nao", "robofun")
                authenticated = True
            except paramiko.AuthenticationException:
                pass

        # ── Method 3: public key ─────────────────────────────────────────────
        if not authenticated:
            for key_file in ("id_ed25519", "id_rsa", "id_ecdsa"):
                key_path = Path.home() / ".ssh" / key_file
                if not key_path.exists():
                    continue
                try:
                    if key_file.startswith("id_ed25519"):
                        key = paramiko.Ed25519Key.from_private_key_file(str(key_path))
                    elif key_file.startswith("id_ecdsa"):
                        key = paramiko.ECDSAKey.from_private_key_file(str(key_path))
                    else:
                        key = paramiko.RSAKey.from_private_key_file(str(key_path))
                    transport.auth_publickey("nao", key)
                    authenticated = True
                    break
                except Exception:
                    pass

        if not authenticated:
            raise paramiko.AuthenticationException("all auth methods failed")

        print(f"[TABLET] SSH authenticated to {robot_ip}")
        sftp = paramiko.SFTPClient.from_transport(transport)

    except Exception as exc:
        print(f"[TABLET] SSH connect failed ({exc}) — using laptop URLs (less reliable).")
        if transport:
            try:
                transport.close()
            except Exception:
                pass
        return False

    try:
        sftp_makedirs(sftp, TABLET_REMOTE_DIR)

        deployed = 0
        for f in sorted(deploy_dir.iterdir()):
            if not f.is_file():
                continue
            if f.name in ("build.js", "package.json", "package-lock.json"):
                continue
            data = f.read_bytes()
            if f.name.endswith(".html"):
                data = data.replace(
                    b'fetch("/api/tablet_input"',
                    f'fetch("{dash_url}/api/tablet_input"'.encode(),
                )
                data = data.replace(
                    b"fetch('/api/tablet_input'",
                    f"fetch('{dash_url}/api/tablet_input'".encode(),
                )
            sftp.putfo(io.BytesIO(data), f"{TABLET_REMOTE_DIR}/{f.name}")
            print(f"[TABLET]   deployed {f.name}")
            deployed += 1

        sftp.close()
        transport.close()
        print(f"[TABLET] {deployed} page(s) deployed → http://198.18.0.1/apps/tablet/")
        return True

    except Exception as exc:
        print(f"[TABLET] SFTP deploy failed ({exc}) — using laptop URLs.")
        for obj in (sftp, transport):
            try:
                obj.close()
            except Exception:
                pass
        return False
