"""Session pool managing a shared renderer subprocess.

The ``SessionPool`` starts a single ``plushie --mock --max-sessions N``
process and multiplexes test sessions over it. Each session gets a
unique ID; the pool injects the ``session`` field into outbound messages
and routes inbound responses by the ``session`` field.

Usage::

    pool = SessionPool(mode="mock", max_sessions=8)
    pool.start()

    session_id = pool.register()
    pool.send(session_id, {"type": "snapshot", "tree": tree})
    resp = pool.send_request(session_id, msg, timeout=10.0)

    pool.unregister(session_id)
    pool.stop()
"""

from __future__ import annotations

import itertools
import logging
import threading
from typing import Any

from plushie.connection import Connection
from plushie.protocol import PROTOCOL_VERSION

logger = logging.getLogger("plushie.testing")

_session_counter = itertools.count(1)


class SessionPool:
    """Manages a shared renderer process for concurrent test sessions.

    Uses a ``Connection`` internally for subprocess management and
    wire I/O. Assigns unique session IDs and routes messages by
    the ``session`` field.

    Args:
        mode: Renderer mode (``"mock"`` or ``"headless"``).
        max_sessions: Maximum concurrent sessions.
        binary_path: Explicit path to the plushie binary. Resolved
            automatically if ``None``.
    """

    def __init__(
        self,
        *,
        mode: str = "mock",
        max_sessions: int = 8,
        binary_path: str | None = None,
    ) -> None:
        self._mode = mode
        self._max_sessions = max_sessions
        self._binary_path = binary_path
        self._conn: Connection | None = None
        self._lock = threading.Lock()
        self._sessions: dict[str, _SessionSlot] = {}
        self._next_id = itertools.count(1)

    def start(self) -> None:
        """Start the renderer subprocess and wait for the hello handshake.

        Raises:
            ConnectionError: If the renderer fails to start or handshake.
        """
        conn = Connection.open(
            binary_path=self._binary_path,
            mode=self._mode,
            max_sessions=self._max_sessions,
        )
        # Send initial settings to trigger hello
        from plushie.protocol import settings

        conn.send(settings({"protocol_version": PROTOCOL_VERSION}, session=""))
        conn.wait_hello(timeout=10.0)
        self._conn = conn

    def stop(self) -> None:
        """Stop the renderer subprocess and clean up all sessions."""
        conn = self._conn
        if conn is not None:
            conn.close()
            self._conn = None
        with self._lock:
            self._sessions.clear()

    @property
    def is_alive(self) -> bool:
        """Whether the renderer subprocess is running."""
        conn = self._conn
        return conn is not None and conn.is_alive

    def register(self) -> str:
        """Allocate a new session ID.

        Returns:
            A unique session identifier string.

        Raises:
            RuntimeError: If the pool is full or not started.
        """
        if self._conn is None:
            raise RuntimeError("session pool is not started")

        with self._lock:
            if len(self._sessions) >= self._max_sessions:
                raise RuntimeError(
                    f"session pool is full ({self._max_sessions} sessions). "
                    "Increase max_sessions or release unused sessions."
                )
            sid = f"pool_{next(self._next_id)}"
            self._sessions[sid] = _SessionSlot(session_id=sid)
            return sid

    def unregister(self, session_id: str, *, timeout: float = 10.0) -> None:
        """Release a session, sending Reset to the renderer and waiting for confirmation.

        Args:
            session_id: The session to release.
            timeout: Maximum seconds to wait for reset_response.
        """
        conn = self._conn
        if conn is None:
            with self._lock:
                self._sessions.pop(session_id, None)
            return

        try:
            # Temporarily set session on the connection for the reset
            old_session = conn.session
            conn.session = session_id
            conn.reset_session(timeout=timeout)
            conn.session = old_session
        except Exception:
            logger.debug(
                "reset failed for session %s during unregister",
                session_id,
                exc_info=True,
            )
        finally:
            with self._lock:
                self._sessions.pop(session_id, None)

    def send(self, session_id: str, msg: dict[str, Any]) -> None:
        """Send a fire-and-forget message for a session.

        The ``session`` field is injected automatically.

        Args:
            session_id: Target session.
            msg: Message dict to send.
        """
        conn = self._conn
        if conn is None:
            raise RuntimeError("session pool is not started")

        msg_with_session = {**msg, "session": session_id}
        conn.send(msg_with_session)

    def send_settings(self, session_id: str, settings_dict: dict[str, Any]) -> None:
        """Send a Settings message for a session.

        Args:
            session_id: Target session.
            settings_dict: Application settings.
        """
        from plushie.protocol import settings

        msg = settings(settings_dict, session=session_id)
        conn = self._conn
        if conn is None:
            raise RuntimeError("session pool is not started")
        conn.send(msg)

    def send_snapshot(self, session_id: str, tree: dict[str, Any]) -> None:
        """Send a Snapshot message for a session.

        Args:
            session_id: Target session.
            tree: Complete UI tree.
        """
        from plushie.protocol import snapshot

        msg = snapshot(tree, session=session_id)
        conn = self._conn
        if conn is None:
            raise RuntimeError("session pool is not started")
        conn.send(msg)

    def send_patch(self, session_id: str, ops: list[dict[str, Any]]) -> None:
        """Send a Patch message for a session.

        Args:
            session_id: Target session.
            ops: Patch operations.
        """
        from plushie.protocol import patch

        msg = patch(ops, session=session_id)
        conn = self._conn
        if conn is None:
            raise RuntimeError("session pool is not started")
        conn.send(msg)

    def interact(
        self,
        session_id: str,
        action: str,
        selector: str | None = None,
        payload: dict[str, Any] | None = None,
        *,
        on_step: Any | None = None,
        timeout: float = 30.0,
    ) -> list[Any]:
        """Send an interact message and collect events.

        Routes through the underlying ``Connection.interact`` with
        the session field set.

        Args:
            session_id: Target session.
            action: Interaction type.
            selector: Target selector string (e.g. ``"#button_id"``).
            payload: Action-specific parameters.
            on_step: Callback for headless interact steps.
            timeout: Maximum seconds to wait.

        Returns:
            List of decoded events.
        """
        conn = self._conn
        if conn is None:
            raise RuntimeError("session pool is not started")

        old_session = conn.session
        conn.session = session_id
        try:
            return conn.interact(
                action,
                selector=selector,
                payload=payload,
                on_step=on_step,
                timeout=timeout,
            )
        finally:
            conn.session = old_session

    def query_find(
        self,
        session_id: str,
        selector: str,
        *,
        timeout: float = 10.0,
    ) -> dict[str, Any] | None:
        """Query the renderer for a widget by selector.

        Args:
            session_id: Target session.
            selector: Selector string (``"#id"`` or ``"text content"``).
            timeout: Maximum seconds to wait.

        Returns:
            The node dict if found, or ``None``.
        """
        conn = self._conn
        if conn is None:
            raise RuntimeError("session pool is not started")

        old_session = conn.session
        conn.session = session_id
        try:
            return conn.query_find(selector, timeout=timeout)
        finally:
            conn.session = old_session

    def query_tree(
        self,
        session_id: str,
        *,
        timeout: float = 10.0,
    ) -> dict[str, Any] | None:
        """Query the renderer for the full tree.

        Args:
            session_id: Target session.
            timeout: Maximum seconds to wait.

        Returns:
            The full tree dict, or ``None``.
        """
        conn = self._conn
        if conn is None:
            raise RuntimeError("session pool is not started")

        old_session = conn.session
        conn.session = session_id
        try:
            return conn.query_tree(timeout=timeout)
        finally:
            conn.session = old_session

    def tree_hash(
        self,
        session_id: str,
        name: str,
        *,
        timeout: float = 10.0,
    ) -> dict[str, Any]:
        """Request a tree hash.

        Args:
            session_id: Target session.
            name: Label for this hash capture.
            timeout: Maximum seconds to wait.

        Returns:
            The tree hash response dict.
        """
        conn = self._conn
        if conn is None:
            raise RuntimeError("session pool is not started")

        old_session = conn.session
        conn.session = session_id
        try:
            return conn.compute_tree_hash(name, timeout=timeout)
        finally:
            conn.session = old_session

    def screenshot(
        self,
        session_id: str,
        name: str,
        *,
        width: int = 1024,
        height: int = 768,
        timeout: float = 30.0,
    ) -> dict[str, Any]:
        """Request a screenshot.

        Args:
            session_id: Target session.
            name: Label for this screenshot capture.
            width: Viewport width in pixels.
            height: Viewport height in pixels.
            timeout: Maximum seconds to wait.

        Returns:
            The screenshot response dict.
        """
        conn = self._conn
        if conn is None:
            raise RuntimeError("session pool is not started")

        old_session = conn.session
        conn.session = session_id
        try:
            return conn.take_screenshot(
                name, width=width, height=height, timeout=timeout
            )
        finally:
            conn.session = old_session


class _SessionSlot:
    """Internal tracking for a registered session."""

    __slots__ = ("session_id",)

    def __init__(self, session_id: str) -> None:
        self.session_id = session_id


__all__ = [
    "SessionPool",
]
