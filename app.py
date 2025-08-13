import os, json
from flask import Flask, request, jsonify, make_response
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

DATA_DIR = os.environ.get("DATA_DIR", "/data")  # 在 Railway 建 Volume 掛載 /data
os.makedirs(DATA_DIR, exist_ok=True)

ICE_CREAM_FILE = os.path.join(DATA_DIR, "ice_cream_selection.json")
EVENTS_FILE    = os.path.join(DATA_DIR, "events.json")

def load_json(path, default):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except Exception:
                return default
    return default

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

@app.route("/get_ice_cream_selection", methods=["GET"])
def get_ice_cream_selection():
    data = load_json(ICE_CREAM_FILE, {})
    if not all(k in data for k in ["ice_cream_1","ice_cream_2","ice_cream_1_english","ice_cream_2_english"]):
        return jsonify({"status":"error","message":"尚未選擇冰淇淋口味"}), 400
    payload = {
        "status":"success",
        "ice_cream_1": data["ice_cream_1"],
        "ice_cream_2": data["ice_cream_2"],
        "ice_cream_1_english": data["ice_cream_1_english"],
        "ice_cream_2_english": data["ice_cream_2_english"],
    }
    resp = make_response(json.dumps(payload, ensure_ascii=False))
    resp.headers["Content-Type"] = "application/json; charset=utf-8"
    return resp

@app.route("/add_ice_cream", methods=["POST"])
def add_ice_cream():
    body = request.get_json(force=True)
    ic1  = body.get("ice_cream_1")
    ic2  = body.get("ice_cream_2")
    ic1e = body.get("ice_cream_1_english")
    ic2e = body.get("ice_cream_2_english")

    if not (ic1 or ic2):
        return jsonify({"status":"error","message":"至少需要選擇一個冰淇淋口味"}), 400

    current = load_json(ICE_CREAM_FILE, {})
    current["ice_cream_1"] = ic1 if ic1 else current.get("ice_cream_1","無資料")
    current["ice_cream_2"] = ic2 if ic2 else current.get("ice_cream_2","無資料")
    current["ice_cream_1_english"] = ic1e if ic1e else current.get("ice_cream_1_english","無資料")
    current["ice_cream_2_english"] = ic2e if ic2e else current.get("ice_cream_2_english","無資料")

    save_json(ICE_CREAM_FILE, current)
    return jsonify({"status":"success","message":"冰淇淋口味已更新"})

@app.route("/get_events", methods=["GET"])
def get_events():
    events = load_json(EVENTS_FILE, [])
    return jsonify({"status":"success","events": events})

@app.route("/submit_event", methods=["POST"])
def submit_event():
    body = request.get_json(force=True)
    text = (body.get("event") or "").strip()
    if not text:
        return jsonify({"status":"error","message":"活動不得為空"}), 400
    events = load_json(EVENTS_FILE, [])
    events.append(text)
    save_json(EVENTS_FILE, events)
    return jsonify({"status":"success","message":"活動新增成功"})

@app.route("/delete_event", methods=["POST"])
def delete_event():
    body = request.get_json(force=True)
    text = (body.get("event") or "").strip()
    events = load_json(EVENTS_FILE, [])
    if text in events:
        events.remove(text)
        save_json(EVENTS_FILE, events)
        return jsonify({"status":"success","message":"活動刪除成功"})
    return jsonify({"status":"error","message":"活動不存在"}), 400
