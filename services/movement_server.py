import uuid
from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit, join_room, leave_room

app = Flask(__name__)
app.config['SECRET_KEY'] = 'aljazari-move-only'
socketio = SocketIO(app, cors_allowed_origins="*")

# device_id -> sid
ONLINE_DEVICES = {}

ROOM_PREFIX = "dev::"

def get_room_for(device_id: str) -> str:
    return ROOM_PREFIX + device_id

# ----------------- Socket.IO Events -----------------

@socketio.on('connect')
def on_connect():
    print("[CONNECT]", request.sid)

@socketio.on('disconnect')
def on_disconnect():
    print("[DISCONNECT]", request.sid)
    # اشطب أي device مربوط بهذا sid
    to_delete = []
    for dev_id, sid in ONLINE_DEVICES.items():
        if sid == request.sid:
            to_delete.append(dev_id)
    for dev_id in to_delete:
        del ONLINE_DEVICES[dev_id]
        print(f"[OFFLINE] {dev_id}")

@socketio.on('register')
def on_register(data):
    """
    data = {
      "device_id": "owner_phone_1001_move" أو "robot_move_1001",
      "device_type": "phone" أو "robot",
      "display_name": "أي نص"
    }
    """
    device_id   = (data or {}).get("device_id")
    device_type = (data or {}).get("device_type")
    print(f"[REGISTER] device_id={device_id}, type={device_type}, sid={request.sid}")

    if not device_id:
        return

    ONLINE_DEVICES[device_id] = request.sid
    room = get_room_for(device_id)
    join_room(room)
    emit("registered", {"ok": True, "device_id": device_id})
    # فقط للوج
    print("[ONLINE]", ONLINE_DEVICES)

@socketio.on('remote_control')
def on_remote_control(data):
    """
    data = {
      "from": "owner_phone_1001_move",
      "to": "robot_move_1001",
      "ctrl_type": "move" | "turn" | "stop",
      "value": 0.3,
      "duration_ms": 800
    }
    """
    frm      = (data or {}).get("from")
    to       = (data or {}).get("to")
    ctrl     = (data or {}).get("ctrl_type")
    value    = float((data or {}).get("value", 0.0))
    duration = int((data or {}).get("duration_ms", 0))

    print(f"[REMOTE_CTRL] from={frm} -> to={to} type={ctrl} value={value} dur={duration}")

    if not to:
        return

    if to not in ONLINE_DEVICES:
        print(f"[REMOTE_CTRL] target {to} OFFLINE")
        emit("remote_ack", {"ok": False, "reason": "robot_offline"}, room=request.sid)
        return

    # ابعث نفس الحدث للروبوت فقط
    room = get_room_for(to)
    emit("remote_control", {
        "from": frm,
        "to": to,
        "ctrl_type": ctrl,
        "value": value,
        "duration_ms": duration
    }, room=room)

    emit("remote_ack", {"ok": True}, room=request.sid)

# ----------------- HTTP Debug Endpoint (اختياري) -----------------
@app.route("/ping")
def ping():
    return jsonify({"ok": True, "msg": "movement server alive"})

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", "6001"))
    print(f"🚀 Movement server on http://0.0.0.0:{port}")
    socketio.run(app, host="0.0.0.0", port=port)
