"""WebSocket bridge between browser clients and ACP sessions."""

import asyncio
import logging
from typing import Any, Dict, Optional

from fastapi import WebSocket, WebSocketDisconnect

from .acp_manager import ACPManager

logger = logging.getLogger(__name__)


class ACPBridge:
    """Bridges browser WebSocket connections to a shared ACP session.

    Single-user workbench: one ACP session is shared across all browser
    WebSocket connections.  When a new WebSocket connects it inherits the
    existing session; when the last WebSocket disconnects the session stays
    alive for fast reconnection.
    """

    def __init__(self, manager: ACPManager):
        self.manager = manager
        self._shared_session_id: Optional[str] = None
        self._active_ws: Optional[WebSocket] = None  # current browser connection
        self._prompt_tasks: Dict[str, asyncio.Task] = {}
        self._lock = asyncio.Lock()
        self.available_commands: list = []
        self._setup_handlers()

    def _setup_handlers(self) -> None:
        """Register notification handlers with ACP manager."""
        # Handle session updates (agent thinking, tool calls, results, etc.)
        self.manager.on_notification("session/update", self._handle_session_update)

        # Handle permission requests
        self.manager.on_notification(
            "session/permission_request", self._handle_permission_request
        )

    async def _handle_session_update(self, params: Dict[str, Any]) -> None:
        """Forward session/update notifications to the active browser WebSocket."""
        session_id = params.get("sessionId")
        if not session_id:
            return

        async with self._lock:
            ws = self._active_ws

        if ws:
            try:
                payload = {"type": "update", "sessionId": session_id}
                payload.update(params)
                await ws.send_json(payload)
                update_type = params.get("update", {}).get("sessionUpdate", "?")
                if update_type == "available_commands_update":
                    cmds = params.get("update", {}).get("availableCommands", [])
                    self.available_commands = cmds
                    print(f"[BRIDGE] available_commands ({len(cmds)})", flush=True)
                else:
                    print(f"[BRIDGE] update: {update_type}", flush=True)
            except Exception as e:
                logger.error(f"Error forwarding update: {e}")

    async def _handle_permission_request(self, params: Dict[str, Any]) -> None:
        """Forward permission requests to the active browser WebSocket."""
        async with self._lock:
            ws = self._active_ws

        if ws:
            try:
                await ws.send_json({
                    "type": "permission_request",
                    "sessionId": params.get("sessionId"),
                    "requestId": params.get("requestId"),
                    "tool": params.get("tool"),
                    "action": params.get("action"),
                    "details": params.get("details", {}),
                })
            except Exception as e:
                logger.error(f"Error forwarding permission request: {e}")

    async def _ensure_session(self) -> str:
        """Get or create the shared ACP session."""
        if self._shared_session_id and self._shared_session_id in self.manager.sessions:
            return self._shared_session_id

        session_id = await self.manager.create_session()
        self._shared_session_id = session_id
        print(f"[BRIDGE] Created shared session {session_id}", flush=True)
        return session_id

    async def handle_websocket(self, websocket: WebSocket) -> None:
        """Main WebSocket handler — all connections share one ACP session."""
        await websocket.accept()
        print("[BRIDGE] New WebSocket connection", flush=True)

        try:
            # Get or create shared session
            session_id = await self._ensure_session()

            async with self._lock:
                self._active_ws = websocket

            # Tell the browser which session it's using
            await websocket.send_json({
                "type": "session_created",
                "sessionId": session_id,
            })

            # Message loop
            while True:
                data = await websocket.receive_json()
                print(f"[BRIDGE] msg: {data.get('type', '?')}", flush=True)
                await self._handle_message(session_id, data, websocket)

        except WebSocketDisconnect:
            print("[BRIDGE] WebSocket disconnected", flush=True)
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
            try:
                await websocket.send_json({"type": "error", "message": str(e)})
            except Exception:
                pass
        finally:
            async with self._lock:
                if self._active_ws is websocket:
                    self._active_ws = None

    async def _handle_message(
        self, session_id: str, data: Dict[str, Any], ws: WebSocket
    ) -> None:
        """Route browser messages to appropriate ACP calls.

        Args:
            session_id: Current session ID
            data: Message data from browser
            ws: WebSocket connection
        """
        msg_type = data.get("type", "")

        logger.debug(f"Handling message type '{msg_type}' for session {session_id}")

        try:
            if msg_type == "prompt":
                await self._handle_prompt(session_id, data)

            elif msg_type == "cancel":
                await self._handle_cancel(session_id)

            elif msg_type == "permission_response":
                await self._handle_permission_response(session_id, data)

            elif msg_type == "ping":
                # Simple keepalive
                await ws.send_json({"type": "pong"})

            else:
                logger.warning(f"Unknown message type: {msg_type}")
                await ws.send_json(
                    {
                        "type": "error",
                        "error": f"Unknown message type: {msg_type}",
                    }
                )

        except Exception as e:
            logger.error(f"Error handling message type '{msg_type}': {e}")
            await ws.send_json(
                {
                    "type": "error",
                    "message": str(e),
                }
            )

    async def _handle_prompt(self, session_id: str, data: Dict[str, Any]) -> None:
        """Handle prompt message — runs as background task for responsiveness."""
        text = data.get("text", "")
        plugin = data.get("plugin", "")
        view = data.get("view", "")

        if not text:
            raise ValueError("Prompt text is required")

        if plugin:
            context_parts = [
                f"You are the UI agent for the {plugin} plugin.",
                "Execute commands and return results as A2UI JSON.",
            ]
            if view:
                context_parts.append(f"The user is viewing the '{view}' view.")
            context_parts.append(f"User request: {text}")
            full_text = " ".join(context_parts)
        else:
            full_text = text

        print(f"[BRIDGE] prompt → {full_text[:80]}...", flush=True)

        async def _run_prompt():
            try:
                result = await self.manager.prompt(session_id, full_text)
                stop_reason = result.get("stopReason", "end_turn") if result else "end_turn"
                async with self._lock:
                    ws = self._active_ws
                if ws:
                    await ws.send_json({
                        "type": "complete",
                        "sessionId": session_id,
                        "stopReason": stop_reason,
                    })
            except Exception as e:
                logger.error(f"Prompt failed: {e}")
                async with self._lock:
                    ws = self._active_ws
                if ws:
                    try:
                        await ws.send_json({"type": "error", "message": str(e)})
                    except Exception:
                        pass
            finally:
                self._prompt_tasks.pop(session_id, None)

        # Cancel any existing prompt
        existing = self._prompt_tasks.get(session_id)
        if existing and not existing.done():
            existing.cancel()

        self._prompt_tasks[session_id] = asyncio.create_task(_run_prompt())

    async def _handle_cancel(self, session_id: str) -> None:
        """Handle cancel message from browser.

        Args:
            session_id: Current session ID
        """
        logger.info(f"Cancelling session {session_id}")
        await self.manager.cancel_session(session_id)

    async def _handle_permission_response(
        self, session_id: str, data: Dict[str, Any]
    ) -> None:
        """Handle permission response from browser.

        Args:
            session_id: Current session ID
            data: Permission response data
        """
        request_id = data.get("requestId")
        approved = data.get("approved", False)

        if not request_id:
            raise ValueError("requestId is required for permission_response")

        logger.info(
            f"Permission response for session {session_id}: "
            f"request={request_id}, approved={approved}"
        )

        await self.manager.send_request(
            "session/resolve_permission",
            {
                "sessionId": session_id,
                "requestId": request_id,
                "approved": approved,
            },
        )

    async def broadcast(self, message: Dict[str, Any]) -> bool:
        """Send a message to the active WebSocket connection."""
        async with self._lock:
            ws = self._active_ws

        if ws:
            try:
                await ws.send_json(message)
                return True
            except Exception as e:
                logger.error(f"Error broadcasting: {e}")
        return False

    @property
    def has_active_connection(self) -> bool:
        return self._active_ws is not None
