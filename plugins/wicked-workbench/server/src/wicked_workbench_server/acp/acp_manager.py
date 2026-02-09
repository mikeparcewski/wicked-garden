"""Manages claude-code-acp subprocess lifecycle and JSON-RPC communication."""

import asyncio
import json
import logging
import shutil
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class ACPManager:
    """Manages claude-code-acp subprocess lifecycle and JSON-RPC protocol."""

    def __init__(self):
        """Initialize the ACP manager."""
        self.process: Optional[asyncio.subprocess.Process] = None
        self.sessions: Dict[str, Dict[str, Any]] = {}
        self._reader_task: Optional[asyncio.Task] = None
        self._pending: Dict[int, asyncio.Future] = {}
        self._next_id: int = 1
        self._notification_handlers: Dict[str, List[Callable]] = {}
        self._initialized = False
        self._lock = asyncio.Lock()
        self._stderr_task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        """Spawn claude-code-acp subprocess."""
        if self.process is not None:
            logger.warning("ACP process already running")
            return

        # Try to find claude-code-acp binary
        binary = shutil.which("claude-code-acp")
        if not binary:
            # Fallback to npx
            binary = "npx"
            cmd = [binary, "@zed-industries/claude-code-acp"]
        else:
            cmd = [binary]

        logger.info(f"Starting ACP process: {' '.join(cmd)}")

        try:
            self.process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            # Start reader task
            self._reader_task = asyncio.create_task(self._read_loop())

            # Start stderr logger task (store reference for cleanup)
            self._stderr_task = asyncio.create_task(self._log_stderr())

            logger.info(f"ACP process started with PID {self.process.pid}")

        except Exception as e:
            logger.error(f"Failed to start ACP process: {e}")
            raise

    async def stop(self) -> None:
        """Kill subprocess and cleanup."""
        logger.info("Stopping ACP process")

        # Cancel reader and stderr tasks
        for task in [self._reader_task, self._stderr_task]:
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        # Terminate process
        if self.process:
            try:
                self.process.terminate()
                await asyncio.wait_for(self.process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                logger.warning("ACP process did not terminate, killing")
                self.process.kill()
                await self.process.wait()
            except Exception as e:
                logger.error(f"Error stopping ACP process: {e}")

            self.process = None

        # Reject all pending requests
        for future in self._pending.values():
            if not future.done():
                future.set_exception(Exception("ACP process stopped"))
        self._pending.clear()

        self._initialized = False
        logger.info("ACP process stopped")

    async def send_request(
        self, method: str, params: Dict[str, Any], timeout: float = 30.0
    ) -> Dict[str, Any]:
        """Send JSON-RPC request and await response.

        Args:
            method: JSON-RPC method name
            params: Method parameters
            timeout: Response timeout in seconds (default 30s)

        Returns:
            Response result dictionary

        Raises:
            Exception: If process is not running or request fails
        """
        if self.process is None or self.process.stdin is None:
            raise Exception("ACP process not running")

        async with self._lock:
            request_id = self._next_id
            self._next_id += 1

        request = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params,
        }

        logger.debug(f"Sending request {request_id}: {method}")

        # Create future for response
        future: asyncio.Future = asyncio.get_event_loop().create_future()
        self._pending[request_id] = future

        try:
            # Check process health before writing
            if not self.is_running():
                raise Exception("ACP process has exited")

            # Write request to stdin (with error handling for process death)
            message = json.dumps(request) + "\n"
            try:
                self.process.stdin.write(message.encode())
                await self.process.stdin.drain()
            except (BrokenPipeError, ConnectionResetError, OSError) as write_err:
                raise Exception(f"ACP process stdin write failed: {write_err}")

            # Wait for response with timeout
            result = await asyncio.wait_for(future, timeout=timeout)
            return result

        except asyncio.TimeoutError:
            logger.error(f"Request {request_id} timed out: {method}")
            raise Exception(f"Request timed out: {method}")
        except Exception as e:
            logger.error(f"Request {request_id} failed: {e}")
            raise
        finally:
            self._pending.pop(request_id, None)

    async def send_notification(self, method: str, params: Dict[str, Any]) -> None:
        """Send JSON-RPC notification (no response expected).

        Args:
            method: JSON-RPC method name
            params: Method parameters
        """
        if self.process is None or self.process.stdin is None:
            raise Exception("ACP process not running")

        notification = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
        }

        logger.debug(f"Sending notification: {method}")

        message = json.dumps(notification) + "\n"
        self.process.stdin.write(message.encode())
        await self.process.stdin.drain()

    async def _read_loop(self) -> None:
        """Read stdout and route responses/notifications."""
        if self.process is None or self.process.stdout is None:
            return

        logger.info("Started ACP stdout reader loop")

        try:
            while True:
                line = await self.process.stdout.readline()
                if not line:
                    logger.warning("ACP process stdout closed")
                    break

                try:
                    message = json.loads(line.decode().strip())
                    await self._handle_message(message)
                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON from ACP: {e}")
                    logger.debug(f"Raw line: {line!r}")
                except Exception as e:
                    logger.error(f"Error handling ACP message: {e}")

        except asyncio.CancelledError:
            logger.info("ACP reader loop cancelled")
            raise
        except Exception as e:
            logger.error(f"ACP reader loop error: {e}")
        finally:
            logger.info("ACP reader loop ended")

    async def _log_stderr(self) -> None:
        """Log stderr output from ACP process."""
        if self.process is None or self.process.stderr is None:
            return

        try:
            while True:
                line = await self.process.stderr.readline()
                if not line:
                    break
                logger.warning(f"ACP stderr: {line.decode().strip()}")
        except Exception as e:
            logger.error(f"Error reading ACP stderr: {e}")

    async def _handle_message(self, message: Dict[str, Any]) -> None:
        """Route JSON-RPC message to appropriate handler.

        Args:
            message: Parsed JSON-RPC message
        """
        # Response to a request (has 'id' field)
        if "id" in message:
            request_id = message["id"]
            future = self._pending.get(request_id)

            if future and not future.done():
                if "error" in message:
                    error = message["error"]
                    logger.error(f"Request {request_id} error: {error}")
                    future.set_exception(
                        Exception(f"JSON-RPC error: {error.get('message', 'Unknown error')}")
                    )
                elif "result" in message:
                    logger.debug(f"Request {request_id} completed successfully")
                    future.set_result(message["result"])
                else:
                    logger.error(f"Invalid response for request {request_id}")
                    future.set_exception(Exception("Invalid JSON-RPC response"))
            else:
                logger.warning(f"Received response for unknown request {request_id}")

        # Notification (has 'method' field, no 'id')
        elif "method" in message:
            method = message["method"]
            params = message.get("params", {})

            logger.debug(f"Received notification: {method}")

            handlers = self._notification_handlers.get(method, [])
            for handler in handlers:
                try:
                    # Call handler (may be sync or async)
                    result = handler(params)
                    if asyncio.iscoroutine(result):
                        await result
                except Exception as e:
                    logger.error(f"Error in notification handler for {method}: {e}")

        else:
            logger.warning(f"Unknown message type: {message}")

    async def initialize(self) -> Dict[str, Any]:
        """Send ACP initialize request.

        Returns:
            Server capabilities and info
        """
        logger.info("Initializing ACP protocol")

        result = await self.send_request(
            "initialize",
            {
                "protocolVersion": 1,
                "clientCapabilities": {
                    "fs": {"readTextFile": True, "writeTextFile": True},
                    "terminal": True,
                },
                "clientInfo": {
                    "name": "wicked-workbench",
                    "title": "Wicked Workbench Dynamic UI",
                    "version": "0.3.0",
                },
            },
        )

        self._initialized = True
        logger.info("ACP protocol initialized successfully")
        return result

    async def create_session(self, cwd: Optional[str] = None) -> str:
        """Create new ACP session.

        Args:
            cwd: Working directory for the Claude Code agent.
                 Defaults to the wicked-garden project root (for plugin access),
                 or falls back to the user's home directory.

        Returns:
            Session ID string

        Raises:
            Exception: If not initialized or session creation fails
        """
        if not self._initialized:
            raise Exception("ACP not initialized")

        # Default to wicked-garden project root so the agent has access to plugins.
        # The project root is detected by walking up from this file's location.
        if not cwd:
            cwd = self._find_project_root()

        print(f"[ACP] Creating session with cwd={cwd}", flush=True)

        result = await self.send_request("session/new", {
            "cwd": cwd,
            "mcpServers": [],
        })
        session_id = result.get("sessionId", "")

        if not session_id:
            raise Exception("Failed to create session: no sessionId in response")

        self.sessions[session_id] = {"created_at": asyncio.get_event_loop().time()}
        logger.info(f"Created ACP session: {session_id}")

        return session_id

    async def prompt(
        self, session_id: str, text: str, context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Send prompt to session and wait for completion.

        The session/prompt request returns a PromptResponse when the turn ends.
        During the turn, session/update notifications stream results.

        Args:
            session_id: Target session ID
            text: Prompt text
            context: Optional context dictionary (currently unused)

        Returns:
            PromptResponse dict with stopReason
        """
        if session_id not in self.sessions:
            raise Exception(f"Unknown session: {session_id}")

        logger.info(f"Sending prompt to session {session_id}")
        logger.debug(f"Prompt text: {text[:100]}...")

        # Use longer timeout for prompts — Claude can take minutes
        return await self.send_request(
            "session/prompt",
            {
                "sessionId": session_id,
                "prompt": [{"type": "text", "text": text}],
            },
            timeout=300.0,  # 5 minutes
        )

    async def cancel_session(self, session_id: str) -> None:
        """Cancel in-flight prompt.

        Args:
            session_id: Target session ID
        """
        if session_id not in self.sessions:
            logger.warning(f"Attempted to cancel unknown session: {session_id}")
            return

        logger.info(f"Cancelling session {session_id}")

        await self.send_notification("session/cancel", {"sessionId": session_id})

    async def end_session(self, session_id: str) -> None:
        """End a session and clean up locally.

        Note: ACP does not have a session/end method, so we only
        clean up local state. The ACP subprocess manages session
        lifecycle internally.

        Args:
            session_id: Target session ID
        """
        if session_id not in self.sessions:
            logger.warning(f"Attempted to end unknown session: {session_id}")
            return

        logger.info(f"Ending session {session_id} (local cleanup)")
        self.sessions.pop(session_id, None)

    def on_notification(self, method: str, handler: Callable) -> None:
        """Register handler for ACP notifications (e.g., session/update).

        Args:
            method: Notification method name
            handler: Callback function (sync or async)
        """
        if method not in self._notification_handlers:
            self._notification_handlers[method] = []

        self._notification_handlers[method].append(handler)
        logger.debug(f"Registered handler for notification: {method}")

    @staticmethod
    def _find_project_root() -> str:
        """Walk up from this file to find the wicked-garden project root.

        Looks for the `.claude` directory as a marker. Falls back to home.
        """
        current = Path(__file__).resolve()
        for parent in current.parents:
            if (parent / ".claude").is_dir() and (parent / "plugins").is_dir():
                return str(parent)
        return str(Path.home())

    def is_running(self) -> bool:
        """Check if ACP process is running.

        Returns:
            True if process is alive
        """
        return (
            self.process is not None
            and self.process.returncode is None
        )
