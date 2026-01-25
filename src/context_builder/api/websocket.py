"""WebSocket connection manager for pipeline progress updates.

This module provides WebSocket connection management for real-time
updates during pipeline execution.
"""

from typing import Dict, List

from fastapi import WebSocket


class ConnectionManager:
    """Manage WebSocket connections for pipeline progress updates."""

    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, run_id: str) -> None:
        """Accept and track a WebSocket connection.

        Args:
            websocket: The WebSocket connection to accept.
            run_id: The run ID to associate with this connection.
        """
        await websocket.accept()
        if run_id not in self.active_connections:
            self.active_connections[run_id] = []
        self.active_connections[run_id].append(websocket)

    def disconnect(self, websocket: WebSocket, run_id: str) -> None:
        """Remove a WebSocket connection.

        Args:
            websocket: The WebSocket connection to remove.
            run_id: The run ID associated with this connection.
        """
        if run_id in self.active_connections:
            if websocket in self.active_connections[run_id]:
                self.active_connections[run_id].remove(websocket)

    async def broadcast(self, run_id: str, message: dict) -> None:
        """Broadcast message to all connections for a run.

        Args:
            run_id: The run ID to broadcast to.
            message: The message dictionary to send.
        """
        if run_id not in self.active_connections:
            return
        disconnected = []
        for connection in self.active_connections[run_id]:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.append(connection)
        # Clean up disconnected
        for conn in disconnected:
            self.disconnect(conn, run_id)


# Global singleton instance
ws_manager = ConnectionManager()
