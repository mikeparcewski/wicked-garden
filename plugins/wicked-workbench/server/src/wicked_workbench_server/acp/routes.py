"""FastAPI routes for ACP Bridge."""

import logging
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from .acp_bridge import ACPBridge
from .acp_manager import ACPManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/acp", tags=["acp"])

# Global instances (initialized in lifespan)
manager: Optional[ACPManager] = None
bridge: Optional[ACPBridge] = None


async def init_acp() -> None:
    """Initialize ACP manager and bridge.

    Should be called during application startup.
    """
    global manager, bridge

    logger.info("Initializing ACP Bridge")

    try:
        manager = ACPManager()
        bridge = ACPBridge(manager)

        await manager.start()
        await manager.initialize()

        logger.info("ACP Bridge initialized successfully")

    except Exception as e:
        logger.error(f"Failed to initialize ACP Bridge: {e}")
        # Clean up on failure
        if manager:
            try:
                await manager.stop()
            except Exception:
                pass
        manager = None
        bridge = None
        raise


async def cleanup_acp() -> None:
    """Clean up ACP manager and bridge.

    Should be called during application shutdown.
    """
    global manager, bridge

    logger.info("Cleaning up ACP Bridge")

    if manager:
        try:
            await manager.stop()
        except Exception as e:
            logger.error(f"Error stopping ACP manager: {e}")

    manager = None
    bridge = None

    logger.info("ACP Bridge cleaned up")


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """WebSocket endpoint for browser connections.

    Args:
        websocket: WebSocket connection from browser

    Protocol:
        Browser -> Server:
            {"type": "prompt", "text": "...", "plugin": "...", "view": "..."}
            {"type": "cancel"}
            {"type": "permission_response", "requestId": "...", "approved": true/false}
            {"type": "ping"}

        Server -> Browser:
            {"type": "session_created", "sessionId": "..."}
            {"type": "update", "sessionId": "...", "data": {...}}
            {"type": "permission_request", "sessionId": "...", "requestId": "...", ...}
            {"type": "pong"}
            {"type": "error", "error": "..."}
    """
    if bridge is None:
        logger.error("WebSocket connection rejected: ACP not initialized")
        await websocket.close(code=1013, reason="ACP not initialized")
        return

    try:
        await bridge.handle_websocket(websocket)
    except WebSocketDisconnect:
        # Normal disconnection, already logged in bridge
        pass
    except Exception as e:
        logger.error(f"Unexpected error in WebSocket endpoint: {e}")


@router.get("/status")
async def acp_status() -> dict:
    """Get ACP Bridge status.

    Returns:
        Status dictionary with:
            - status: "running", "stopped", or "not_initialized"
            - sessions: list of active session IDs
            - process_pid: PID of claude-code-acp process (if running)
    """
    if manager is None:
        return {
            "status": "not_initialized",
            "sessions": [],
            "process_pid": None,
        }

    is_running = manager.is_running()
    process_pid = manager.process.pid if manager.process else None

    return {
        "status": "running" if is_running else "stopped",
        "connected": bridge.has_active_connection if bridge else False,
        "process_pid": process_pid,
        "session_count": len(manager.sessions),
    }


@router.post("/restart")
async def restart_acp() -> dict:
    """Restart ACP Bridge.

    Returns:
        Status dictionary after restart
    """
    global manager, bridge

    logger.info("Restarting ACP Bridge")

    try:
        # Clean up existing
        await cleanup_acp()

        # Reinitialize
        await init_acp()

        return {
            "status": "restarted",
            "message": "ACP Bridge restarted successfully",
        }

    except Exception as e:
        logger.error(f"Failed to restart ACP Bridge: {e}")
        return {
            "status": "error",
            "error": str(e),
        }


@router.post("/broadcast")
async def broadcast_message(message: dict) -> dict:
    """Broadcast a message to all connected sessions.

    Args:
        message: Message dictionary to broadcast

    Returns:
        Result dictionary with recipient count
    """
    if bridge is None:
        return {
            "status": "error",
            "error": "ACP not initialized",
            "recipients": 0,
        }

    try:
        sent = await bridge.broadcast(message)
        return {
            "status": "success",
            "sent": sent,
        }
    except Exception as e:
        logger.error(f"Error broadcasting message: {e}")
        return {
            "status": "error",
            "error": str(e),
        }


@router.get("/commands")
async def list_commands() -> dict:
    """Get available slash commands from the ACP agent.

    These are discovered automatically when the first session is created.
    The list is cached and served to the frontend for dynamic UI generation.

    Returns:
        Dictionary with commands grouped by plugin
    """
    if bridge is None:
        return {"commands": [], "grouped": {}, "count": 0}

    commands = bridge.available_commands

    # Group by plugin (commands like "wicked-mem:stats" → plugin="wicked-mem")
    grouped: dict = {}
    for cmd in commands:
        name = cmd.get("name", "")
        if ":" in name:
            plugin, _, cmd_name = name.partition(":")
            if plugin not in grouped:
                grouped[plugin] = []
            grouped[plugin].append({
                "name": cmd_name,
                "fullName": name,
                "description": cmd.get("description", ""),
                "input": cmd.get("input"),
            })
        else:
            if "_project" not in grouped:
                grouped["_project"] = []
            grouped["_project"].append({
                "name": name,
                "fullName": name,
                "description": cmd.get("description", ""),
                "input": cmd.get("input"),
            })

    return {
        "commands": commands,
        "grouped": grouped,
        "count": len(commands),
    }


@router.get("/sessions")
async def list_sessions() -> dict:
    """Get shared session info."""
    if manager is None or bridge is None:
        return {"session": None, "connected": False}

    sid = bridge._shared_session_id
    if sid:
        info = manager.sessions.get(sid, {})
        return {
            "session": {"sessionId": sid, "createdAt": info.get("created_at")},
            "connected": bridge.has_active_connection,
        }
    return {"session": None, "connected": bridge.has_active_connection}


@router.delete("/sessions/{session_id}")
async def end_session(session_id: str) -> dict:
    """End a specific session.

    Args:
        session_id: Session ID to end

    Returns:
        Result dictionary
    """
    if manager is None:
        return {
            "status": "error",
            "error": "ACP not initialized",
        }

    try:
        await manager.end_session(session_id)
        return {
            "status": "success",
            "message": f"Session {session_id} ended",
        }
    except Exception as e:
        logger.error(f"Error ending session {session_id}: {e}")
        return {
            "status": "error",
            "error": str(e),
        }
