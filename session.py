#!/usr/bin/env python
# =============================================================================
#                     HRI_lab_Pepper — Session Singleton
# =============================================================================
"""
Manages a single qi.Session for the whole process.

Usage
-----
    from HRI_lab_Pepper.session import PepperSession

    sess = PepperSession.connect("tcp://172.18.48.50:9559")
    # … later in any module:
    sess = PepperSession.get()
"""
import pathlib
import socket
import sys
import threading
try:
    import qi
except ImportError:
    qi = None  # type: ignore[assignment]

from HRI_lab_Pepper.config import B, W, R


# ── SSH reverse-tunnel helpers ────────────────────────────────────────────────

def _find_free_local_port() -> int:
    """Return an available TCP port on localhost (closes the socket immediately)."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _handle_tunnel_channel(chan, local_port: int) -> None:
    """Forward a paramiko Channel ↔ local TCP port."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # TCP_NODELAY is critical for qi/NAOqi: it's a request-response protocol
    # with small packets.  Without this, Nagle's algorithm buffers outgoing
    # data on the relay socket for up to 40 ms, tripping qi's internal timeout.
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    try:
        sock.connect(("127.0.0.1", local_port))
    except Exception:
        chan.close()
        return

    def _pipe(src_recv, dst_send):
        try:
            while True:
                data = src_recv(65536)
                if not data:
                    break
                dst_send(data)
        except Exception:
            pass
        finally:
            try: sock.close()
            except Exception: pass
            try: chan.close()
            except Exception: pass

    threading.Thread(target=_pipe, args=(chan.recv, sock.sendall), daemon=True).start()
    threading.Thread(target=_pipe, args=(sock.recv, chan.sendall), daemon=True).start()


class _TunnelDispatcher:
    """
    Single paramiko TCP handler that routes incoming reverse-tunnel connections
    to the correct local port based on the SSH server-side (listen) port.

    **Why this is needed**: ``paramiko.Transport._tcp_handler`` is a *single
    slot* — every call to ``request_port_forward(..., handler=fn)`` overwrites
    the previous value.  If we register two ports (e.g. qi service and HTTP)
    with different handler closures, the second call silently replaces the
    first, so all connections — regardless of which robot-side port they arrive
    on — are forwarded to the second port's target (uvicorn, in our case).
    Using one dispatcher keeps ``_tcp_handler`` stable across all registrations
    and dispatches by ``server_port`` instead.
    """

    def __init__(self):
        self._routes: dict = {}   # robot_bound_port → laptop_local_port

    def add_route(self, robot_port: int, laptop_port: int) -> None:
        self._routes[robot_port] = laptop_port

    def __call__(self, chan, origin, server):
        _, server_port = server
        local_port = self._routes.get(server_port)
        if local_port is None:
            chan.close()
            return
        threading.Thread(
            target=_handle_tunnel_channel, args=(chan, local_port), daemon=True
        ).start()


def _ssh_reverse_tunnel(robot_ip: str, local_port: int) -> "paramiko.Transport | None":
    """
    Open an SSH connection to *robot_ip* and request a reverse port-forward so
    the robot can reach ``127.0.0.1:<local_port>`` on this machine.

    Returns the live :class:`paramiko.Transport` or ``None`` on failure.
    """
    try:
        import paramiko  # noqa: PLC0415
    except ImportError:
        return None

    try:
        transport = paramiko.Transport((robot_ip, 22))
        # Disable Nagle so qi's tiny control packets are forwarded immediately.
        transport.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        transport.connect()
    except Exception as exc:
        print(f"{W}[PepperSession] SSH tunnel: could not connect to {robot_ip}:22 — {exc}{W}")
        return None

    # ── Authentication ────────────────────────────────────────────────
    def _ki(title, instructions, prompts):
        return ["nao" for _ in prompts]

    authenticated = False
    for _try in [
        lambda: transport.auth_interactive("nao", _ki),
        lambda: transport.auth_password("nao", "nao"),
        lambda: transport.auth_password("nao", "robofun"),
    ]:
        try:
            _try()
            authenticated = True
            break
        except paramiko.AuthenticationException:
            pass

    if not authenticated:
        for key_name in ("id_ed25519", "id_rsa", "id_ecdsa"):
            key_path = pathlib.Path.home() / ".ssh" / key_name
            if not key_path.exists():
                continue
            try:
                if "ed25519" in key_name:
                    key = paramiko.Ed25519Key.from_private_key_file(str(key_path))
                elif "ecdsa" in key_name:
                    key = paramiko.ECDSAKey.from_private_key_file(str(key_path))
                else:
                    key = paramiko.RSAKey.from_private_key_file(str(key_path))
                transport.auth_publickey("nao", key)
                authenticated = True
                break
            except Exception:
                pass

    if not authenticated:
        print(f"{W}[PepperSession] SSH tunnel: authentication failed — falling back.{W}")
        transport.close()
        return None

    # ── Attach dispatcher and register first port-forward ────────────
    dispatcher = _TunnelDispatcher()
    transport._dispatcher = dispatcher

    try:
        bound_port = transport.request_port_forward(
            "127.0.0.1", local_port, handler=dispatcher
        )
    except Exception as exc:
        print(f"{W}[PepperSession] SSH tunnel: port-forward request failed — {exc}{W}")
        transport.close()
        return None

    if bound_port != local_port:
        print(f"{W}[PepperSession] SSH tunnel: robot bound {bound_port} ≠ {local_port} — falling back.{W}")
        transport.close()
        return None

    dispatcher.add_route(bound_port, local_port)
    return transport


# ── Session singleton ─────────────────────────────────────────────────────────


class PepperSession:
    """Singleton wrapper around a qi.Session."""

    _session = None  # type: qi.Session | None
    _cleanup_callbacks: list = []   # registered by modules, called on disconnect
    _ssh_tunnel = None              # paramiko.Transport keeping the reverse tunnel alive

    # ------------------------------------------------------------------
    @classmethod
    def connect(cls, url: str) -> "qi.Session":
        """
        Connect to the robot at *url* (e.g. ``"tcp://172.18.48.50:9559"``).

        Returns the underlying :class:`qi.Session` so callers that need the
        raw session object can use it directly.

        Raises :class:`RuntimeError` if the connection fails.
        """
        if cls._session is not None:
            return cls._session

        if qi is None:
            raise RuntimeError(
                "The 'qi' (Naoqi SDK) package is not installed. "
                "Run from a machine with the Pepper Python SDK."
            )

        robot_host = url.split("://")[-1].split(":")[0]

        # ── Determine listen address ──────────────────────────────────
        # The robot needs to open a TCP connection *back* to this process
        # to use registered services (e.g. PepperAPI_STT / processRemote).
        # On a laptop connected to a different subnet the robot has no route
        # to the laptop's IP, so we set up an SSH reverse tunnel instead:
        #   robot:127.0.0.1:PORT  →  (SSH)  →  laptop:127.0.0.1:PORT
        # qi then advertises "connect to 127.0.0.1:PORT"; the robot connects
        # to its own loopback which the tunnel transparently forwards here.
        local_port = _find_free_local_port()
        tunnel = _ssh_reverse_tunnel(robot_host, local_port)
        if tunnel is not None:
            cls._ssh_tunnel = tunnel
            listen_addr = f"tcp://127.0.0.1:{local_port}"
            print(f"{B}[PepperSession] SSH tunnel active → listening on {listen_addr}{W}")
        else:
            # Fallback: advertise the IP the OS would use to reach the robot.
            # Works when both machines are on the same subnet (e.g. ethernet).
            _s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                _s.connect((robot_host, 9559))
                _local_ip = _s.getsockname()[0]
            finally:
                _s.close()
            listen_addr = f"tcp://{_local_ip}:0"
            print(f"{B}[PepperSession] No SSH tunnel — listening on {listen_addr}{W}")

        session = qi.Session()
        try:
            session.listen(listen_addr)
            session.connect(url)
        except RuntimeError as exc:
            print(f"{R}[PepperSession] Could not connect to {url}: {exc}{W}")
            raise

        cls._session = session
        print(f"{B}[PepperSession] Connected to {url}{W}")
        return session

    # ------------------------------------------------------------------
    @classmethod
    def get(cls) -> "qi.Session":
        """
        Return the active session.

        Raises :class:`RuntimeError` if :meth:`connect` has not been called.
        """
        if cls._session is None:
            raise RuntimeError(
                "No active Pepper session. Call PepperSession.connect(url) first."
            )
        return cls._session

    # ------------------------------------------------------------------
    @classmethod
    def disable_autonomous_life(cls) -> None:
        """
        Stop all autonomous background behaviours so Pepper stops moving its
        head and eyes randomly, WITHOUT calling setState("disabled") which
        would cause the robot to go to rest/crouch posture.

        Uses ALAutonomousLife.setAutonomousAbilityEnabled() (the correct
        service per Aldebaran docs) and ALMotion idle/breath controls.
        """
        session = cls.get()

        _ABILITIES = [
            "BackgroundMovement",
            "AutonomousBlinking",
            "BasicAwareness",
            "SpeakingMovement",
            "ListeningMovement",
        ]
        try:
            al = session.service("ALAutonomousLife")
            for ability in _ABILITIES:
                try:
                    al.setAutonomousAbilityEnabled(ability, False)
                except Exception:
                    pass
            print(f"{B}[PepperSession] Autonomous abilities disabled.{W}")
        except Exception as exc:
            print(f"{R}[PepperSession] Could not disable autonomous abilities: {exc}{W}")

        try:
            motion = session.service("ALMotion")
            for chain in ["Body", "Head", "Arms", "LArm", "RArm", "Legs"]:
                try:
                    motion.setBreathEnabled(chain, False)
                except Exception:
                    pass
                try:
                    motion.setIdlePostureEnabled(chain, False)
                except Exception:
                    pass
            print(f"{B}[PepperSession] ALMotion breath/idle posture disabled.{W}")
        except Exception as exc:
            print(f"{R}[PepperSession] Could not disable ALMotion idle: {exc}{W}")

    # ------------------------------------------------------------------
    @classmethod
    def enable_autonomous_life(cls) -> None:
        """
        Re-enable ``ALAutonomousLife`` (solitary state) and the standard
        autonomous abilities.
        """
        session = cls.get()
        try:
            al = session.service("ALAutonomousLife")
            al.setState("solitary")
            print(f"{B}[PepperSession] AutonomousLife enabled (solitary).{W}")
        except Exception as exc:
            print(f"{R}[PepperSession] Could not enable AutonomousLife: {exc}{W}")

        _ABILITIES = [
            "BackgroundMovement",
            "AutonomousBlinking",
            "BasicAwareness",
            "SpeakingMovement",
            "ListeningMovement",
        ]
        try:
            al = session.service("ALAutonomousLife")
            for ability in _ABILITIES:
                try:
                    al.setAutonomousAbilityEnabled(ability, True)
                except Exception:
                    pass
            print(f"{B}[PepperSession] Autonomous abilities re-enabled.{W}")
        except Exception as exc:
            print(f"{R}[PepperSession] Could not re-enable autonomous abilities: {exc}{W}")

    # ------------------------------------------------------------------
    @classmethod
    def register_cleanup(cls, callback) -> None:
        """
        Register a zero-argument callable to be called during
        :meth:`disconnect` (in LIFO order) before the session is closed.

        Modules should call this in their ``__init__`` so that their
        service subscriptions are always cleaned up, even if the user
        forgets to call ``stop()`` / ``unsubscribe()`` themselves.

        Example::

            class SomeModule:
                def __init__(self, session):
                    self._svc = session.service("ALSomeService")
                    self._svc.subscribe("MyModule")
                    PepperSession.register_cleanup(self._cleanup)

                def _cleanup(self):
                    try:
                        self._svc.unsubscribe("MyModule")
                    except Exception:
                        pass
        """
        cls._cleanup_callbacks.append(callback)

    # ------------------------------------------------------------------
    @classmethod
    def disconnect(cls) -> None:
        """
        Run all registered cleanup callbacks (LIFO), then close the session.
        """
        if cls._session is None:
            return

        # Call cleanups in reverse registration order (LIFO) so that
        # higher-level modules are torn down before lower-level ones.
        callbacks = list(reversed(cls._cleanup_callbacks))
        cls._cleanup_callbacks.clear()
        for cb in callbacks:
            try:
                cb()
            except Exception as exc:
                print(f"{R}[PepperSession] Cleanup error ({cb}): {exc}{W}")

        try:
            cls._session.close()
        except Exception:
            pass
        cls._session = None

        if cls._ssh_tunnel is not None:
            try:
                cls._ssh_tunnel.close()
            except Exception:
                pass
            cls._ssh_tunnel = None

        print(f"{B}[PepperSession] Disconnected.{W}")
