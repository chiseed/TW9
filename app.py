import os, json
from flask import Flask, request, jsonify, make_response
from flask_cors import CORS
import requests

app = Flask(__name__)
CORS(app)

DATA_DIR = os.environ.get("DATA_DIR", "/data")
os.makedirs(DATA_DIR, exist_ok=True)

ICE_CREAM_FILE = os.path.join(DATA_DIR, "ice_cream_selection.json")
EVENTS_FILE    = os.path.join(DATA_DIR, "events.json")

CWA_API_KEY = "CWA-B139B2EE-63AE-40CF-A7AB-7FC3C3ACA0C5"

def load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default
    return default

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

@app.route("/", methods=["GET"])
def root():
    return "OK", 200

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200

@app.route("/get_ice_cream_selection", methods=["GET"])
def get_ice_cream_selection():
    data = load_json(ICE_CREAM_FILE, {})
    required = ["ice_cream_1", "ice_cream_2", "ice_cream_1_english", "ice_cream_2_english"]
    if not all(k in data for k in required):
        return jsonify({"status": "error", "message": "尚未選擇冰淇淋口味"}), 400

    payload = {
        "status": "success",
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
    body = request.get_json(silent=True) or {}
    ic1  = body.get("ice_cream_1")
    ic2  = body.get("ice_cream_2")
    ic1e = body.get("ice_cream_1_english")
    ic2e = body.get("ice_cream_2_english")

    if not (ic1 or ic2):
        return jsonify({"status": "error", "message": "至少需要選擇一個冰淇淋口味"}), 400

    current = load_json(ICE_CREAM_FILE, {})
    current["ice_cream_1"] = ic1 if ic1 else current.get("ice_cream_1", "無資料")
    current["ice_cream_2"] = ic2 if ic2 else current.get("ice_cream_2", "無資料")
    current["ice_cream_1_english"] = ic1e if ic1e else current.get("ice_cream_1_english", "無資料")
    current["ice_cream_2_english"] = ic2e if ic2e else current.get("ice_cream_2_english", "無資料")

    save_json(ICE_CREAM_FILE, current)
    return jsonify({"status": "success", "message": "冰淇淋口味已更新"})

@app.route("/get_events", methods=["GET"])
def get_events():
    events = load_json(EVENTS_FILE, [])
    return jsonify({"status": "success", "events": events})

@app.route("/submit_event", methods=["POST"])
def submit_event():
    body = request.get_json(silent=True) or {}
    text = (body.get("event") or "").strip()
    if not text:
        return jsonify({"status": "error", "message": "活動不得為空"}), 400

    events = load_json(EVENTS_FILE, [])
    events.append(text)
    save_json(EVENTS_FILE, events)
    return jsonify({"status": "success", "message": "活動新增成功"})

@app.route("/delete_event", methods=["POST"])
def delete_event():
    body = request.get_json(silent=True) or {}
    text = (body.get("event") or "").strip()

    events = load_json(EVENTS_FILE, [])
    if text in events:
        events.remove(text)
        save_json(EVENTS_FILE, events)
        return jsonify({"status": "success", "message": "活動刪除成功"})
    return jsonify({"status": "error", "message": "活動不存在"}), 400

@app.route("/get_weather", methods=["GET"])
def get_weather():
    if not CWA_API_KEY:
        return jsonify({"status": "error", "message": "缺少 CWA_API_KEY"}), 500

    url = "https://opendata.cwa.gov.tw/api/v1/rest/datastore/O-A0001-001"
    params = {
        "Authorization": CWA_API_KEY,
        "locationName": "嘉義市",
    }
    try:
        r = requests.get(url, params=params, timeout=8)
        r.raise_for_status()
        return jsonify(r.json())
    except requests.RequestException as e:
        return jsonify({"status": "error", "message": f"取天氣失敗: {e}"}), 502

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)


