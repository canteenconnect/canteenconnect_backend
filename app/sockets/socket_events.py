from flask import request
from flask_socketio import emit, join_room, leave_room


def register_socket_events(socketio):
    @socketio.on("connect")
    def handle_connect():
        emit(
            "connected",
            {
                "message": "Socket connected.",
                "sid": request.sid,
            },
        )

    @socketio.on("join_room")
    def handle_join_room(data):
        room = (data or {}).get("room")
        if not room:
            emit("socket_error", {"message": "room is required."})
            return
        join_room(room)
        emit("room_joined", {"room": room})

    @socketio.on("leave_room")
    def handle_leave_room(data):
        room = (data or {}).get("room")
        if not room:
            emit("socket_error", {"message": "room is required."})
            return
        leave_room(room)
        emit("room_left", {"room": room})

    @socketio.on("disconnect")
    def handle_disconnect():
        return None

