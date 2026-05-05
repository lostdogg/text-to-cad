"""WebSocket collaboration API."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/collaborate", tags=["collaborate"])


# ------------------------------------------------------------------ #
# Data models                                                         #
# ------------------------------------------------------------------ #

class Participant(BaseModel):
    participant_id: str
    name: str
    color: str
    cursor_position: Optional[Dict[str, float]] = None
    joined_at: str = ""


class CollaborationEvent(BaseModel):
    event_type: str  # join_session | leave_session | update_model | cursor_move | chat_message
    session_id: str
    participant_id: str
    payload: Dict[str, Any] = {}
    timestamp: str = ""


# ------------------------------------------------------------------ #
# Session manager                                                     #
# ------------------------------------------------------------------ #

CURSOR_COLORS = [
    "#FF6B6B", "#4ECDC4", "#45B7D1", "#96CEB4",
    "#FFEAA7", "#DDA0DD", "#98D8C8", "#F7DC6F",
]


class CollaborationManager:
    """Manages real-time collaboration sessions."""

    def __init__(self):
        self.sessions: Dict[str, Dict[str, Any]] = {}  # session_id -> session data
        self.connections: Dict[str, WebSocket] = {}    # participant_id -> websocket

    def create_session(self, session_id: str) -> Dict[str, Any]:
        if session_id not in self.sessions:
            self.sessions[session_id] = {
                "session_id": session_id,
                "participants": {},
                "model_history": [],
                "chat": [],
                "created_at": datetime.utcnow().isoformat(),
            }
        return self.sessions[session_id]

    def add_participant(
        self,
        session_id: str,
        websocket: WebSocket,
        name: Optional[str] = None,
    ) -> Participant:
        session = self.create_session(session_id)
        participant_id = str(uuid.uuid4())[:8]
        color_index = len(session["participants"]) % len(CURSOR_COLORS)
        participant = Participant(
            participant_id=participant_id,
            name=name or f"User-{participant_id}",
            color=CURSOR_COLORS[color_index],
            joined_at=datetime.utcnow().isoformat(),
        )
        session["participants"][participant_id] = participant.dict()
        self.connections[participant_id] = websocket
        return participant

    def remove_participant(self, session_id: str, participant_id: str):
        if session_id in self.sessions:
            self.sessions[session_id]["participants"].pop(participant_id, None)
        self.connections.pop(participant_id, None)

    async def broadcast(
        self,
        session_id: str,
        event: Dict[str, Any],
        exclude: Optional[str] = None,
    ):
        """Broadcast an event to all session participants."""
        if session_id not in self.sessions:
            return
        session = self.sessions[session_id]
        message = json.dumps(event)
        dead = []
        for pid in list(session["participants"].keys()):
            if pid == exclude:
                continue
            ws = self.connections.get(pid)
            if ws:
                try:
                    await ws.send_text(message)
                except Exception:
                    dead.append(pid)
        for pid in dead:
            self.remove_participant(session_id, pid)

    async def send_to(self, participant_id: str, event: Dict[str, Any]):
        ws = self.connections.get(participant_id)
        if ws:
            try:
                await ws.send_text(json.dumps(event))
            except Exception:
                pass

    def get_session_state(self, session_id: str) -> Dict[str, Any]:
        return self.sessions.get(session_id, {})


_manager = CollaborationManager()


def get_manager() -> CollaborationManager:
    return _manager


# ------------------------------------------------------------------ #
# WebSocket endpoint                                                  #
# ------------------------------------------------------------------ #

@router.websocket("/ws/{session_id}")
async def collaborate_ws(websocket: WebSocket, session_id: str):
    """Real-time collaboration WebSocket endpoint."""
    await websocket.accept()
    manager = get_manager()
    participant = manager.add_participant(session_id, websocket)

    # Send welcome
    await websocket.send_text(json.dumps({
        "event_type": "welcome",
        "session_id": session_id,
        "participant": participant.dict(),
        "session_state": manager.get_session_state(session_id),
        "timestamp": datetime.utcnow().isoformat(),
    }))

    # Notify others
    await manager.broadcast(session_id, {
        "event_type": "participant_joined",
        "session_id": session_id,
        "participant": participant.dict(),
        "timestamp": datetime.utcnow().isoformat(),
    }, exclude=participant.participant_id)

    try:
        while True:
            data = await websocket.receive_text()
            try:
                event = json.loads(data)
            except json.JSONDecodeError:
                continue

            event_type = event.get("event_type", "unknown")
            ts = datetime.utcnow().isoformat()
            event["participant_id"] = participant.participant_id
            event["timestamp"] = ts

            if event_type == "cursor_move":
                # Update stored position
                session = manager.sessions.get(session_id, {})
                parts = session.get("participants", {})
                if participant.participant_id in parts:
                    parts[participant.participant_id]["cursor_position"] = event.get("position")
                await manager.broadcast(session_id, event, exclude=participant.participant_id)

            elif event_type == "update_model":
                session = manager.sessions.get(session_id, {})
                session.setdefault("model_history", []).append({
                    "participant_id": participant.participant_id,
                    "model_data": event.get("model_data"),
                    "timestamp": ts,
                })
                await manager.broadcast(session_id, event, exclude=participant.participant_id)

            elif event_type == "chat_message":
                session = manager.sessions.get(session_id, {})
                chat_msg = {
                    "participant_id": participant.participant_id,
                    "participant_name": participant.name,
                    "color": participant.color,
                    "message": event.get("message", ""),
                    "timestamp": ts,
                }
                session.setdefault("chat", []).append(chat_msg)
                await manager.broadcast(session_id, {
                    "event_type": "chat_message",
                    "session_id": session_id,
                    **chat_msg,
                })

            elif event_type == "ping":
                await manager.send_to(participant.participant_id, {
                    "event_type": "pong",
                    "timestamp": ts,
                })

            else:
                await manager.broadcast(session_id, event)

    except WebSocketDisconnect:
        manager.remove_participant(session_id, participant.participant_id)
        await manager.broadcast(session_id, {
            "event_type": "participant_left",
            "session_id": session_id,
            "participant_id": participant.participant_id,
            "timestamp": datetime.utcnow().isoformat(),
        })
