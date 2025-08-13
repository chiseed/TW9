import os
import json
import time
from urllib.parse import quote
from flask import Flask, request, jsonify, make_response, send_from_directory, redirect
from flask_cors import CORS
import requests

app = Flask(__name__)
CORS(app)

# ====== Storage paths ======
DATA_DIR = os.environ.get("DATA_DIR", "/data")
os.makedirs(DATA_DIR, exist_ok=True)

ICE_CREAM_FILE = os.path.join(DATA_DIR, "ice_cream_selection.json")
EVENTS_FILE    = os.path.join(DATA_DIR, "events.json")

# Background metadata + uploads dir
BG_META_FILE   = os.path.join(DATA_DIR, "background.json")
BG_UPLOAD_DIR  = os.path.join(DATA_DIR, "backgrounds")
os.makedirs(BG_UPLOAD_DIR, exist_ok=True)

# Netlify 公網域（可用環境變數覆蓋）
STATIC_PUBLIC_BASE = os.environ.get(
    "STATIC_PUBLIC_BASE",
    "https://gleeful-pie-beaa87.netlify.app"   # ← 改成你的 Netlify 網域即可
)

# Weather API key（你指定要硬編）
CWA_API_KEY = "CWA-B139B2EE-63AE-40CF-A7AB-7FC3C3ACA0C5"

# ====== Helpers ======
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

def public_base():
    proto = request.headers.get("X-Forwarded-Proto", request.scheme)
    host  = request.headers.get("X-Forwarded-Host", request.host)
    return f"{proto}://{host}"

# ====== Health ======
@app.route("/", methods=["GET"])
def root():
    return "OK", 200

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200

# ====== Ice cream ======
@app.route("/get_ice_cream_selection", methods=["GET"])
def get_ice_cream_selection():
    data = load_json(ICE_CREAM_FILE, {})
    req = ["ice_cream_1", "ice_cream_2", "ice_cream_1_english", "ice_cream_2_english"]
    if not all(k in data for k in req):
        return jsonify({"status": "error", "message": "尚未選擇冰淇淋口味"}), 400
    payload = {"status": "success", **{k: data[k] for k in req}}
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
    cur = load_json(ICE_CREAM_FILE, {})
    cur["ice_cream_1"] = ic1 if ic1 else cur.get("ice_cream_1", "無資料")
    cur["ice_cream_2"] = ic2 if ic2 else cur.get("ice_cream_2", "無資料")
    cur["ice_cream_1_english"] = ic1e if ic1e else cur.get("ice_cream_1_english", "無資料")
    cur["ice_cream_2_english"] = ic2e if ic2e else cur.get("ice_cream_2_english", "無資料")
    save_json(ICE_CREAM_FILE, cur)
    return jsonify({"status": "success", "message": "冰淇淋口味已更新"})

# ====== Events ======
@app.route("/get_events", methods=["GET"])
def get_events():
    return jsonify({"status": "success", "events": load_json(EVENTS_FILE, [])})

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

# ====== Weather ======
@app.route("/get_weather", methods=["GET"])
def get_weather():
    location = request.args.get("locationName", "嘉義")
    if not CWA_API_KEY:
        return jsonify({"status": "error", "message": "缺少 CWA_API_KEY"}), 500
    url = "https://opendata.cwa.gov.tw/api/v1/rest/datastore/O-A0001-001"
    params = {"Authorization": CWA_API_KEY, "locationName": location}
    try:
        r = requests.get(url, params=params, timeout=8)
        r.raise_for_status()
        return jsonify(r.json())
    except requests.RequestException as e:
        return jsonify({"status": "error", "message": f"取天氣失敗: {e}"}), 502

# ====== Background: static / upload / url ======
# meta = {"mode": "static"|"upload"|"url", "name": "<filename>", "url":"<http url>"}
def get_bg_meta():
    return load_json(BG_META_FILE, {})

def set_bg_meta(meta):
    save_json(BG_META_FILE, meta)

@app.route("/get_background", methods=["GET"])
def get_background():
    return jsonify({"status": "success", **get_bg_meta()})

@app.route("/set_background", methods=["POST"])
def set_background():
    body = request.get_json(silent=True) or {}
    # Backward compatible: if no type, treat as static filename
    bg_type = (body.get("type") or "").strip().lower()
    if not bg_type and body.get("filename"):
        bg_type = "static"

    if bg_type == "static":
        name = (body.get("name") or body.get("filename") or "").strip()
        if not name:
            return jsonify({"status": "error", "message": "缺少 name/filename"}), 400
        set_bg_meta({"mode": "static", "name": name})
        return jsonify({"status": "success", "message": "背景已切換（static）", "name": name})

    if bg_type == "upload":
        name = (body.get("name") or "").strip()
        if not name or not os.path.isfile(os.path.join(BG_UPLOAD_DIR, name)):
            return jsonify({"status": "error", "message": "上傳檔不存在"}), 400
        set_bg_meta({"mode": "upload", "name": name})
        return jsonify({"status": "success", "message": "背景已切換（upload）", "name": name})

    if bg_type == "url":
        url = (body.get("url") or "").strip()
        if not url:
            return jsonify({"status": "error", "message": "缺少 url"}), 400
        set_bg_meta({"mode": "url", "url": url})
        return jsonify({"status": "success", "message": "背景已切換（url）", "url": url})

    return jsonify({"status": "error", "message": "未知的 type，請用 static / upload / url"}), 400

@app.route("/upload_background", methods=["POST"])
def upload_background():
    # accepts multipart/form-data with field "file"
    if "file" not in request.files:
        return jsonify({"status": "error", "message": "沒有檔案"}), 400
    f = request.files["file"]
    if f.filename == "":
        return jsonify({"status": "error", "message": "檔名為空"}), 400
    name = os.path.basename(f.filename).replace("\\", "_").replace("/", "_")
    target = os.path.join(BG_UPLOAD_DIR, name)
    f.save(target)
    return jsonify({
        "status": "success",
        "message": "上傳完成",
        "name": name,
        "url": f"{public_base()}/background/uploads/{quote(name)}"
    })

@app.route("/list_uploaded_backgrounds", methods=["GET"])
def list_uploaded_backgrounds():
    files = [fn for fn in os.listdir(BG_UPLOAD_DIR) if os.path.isfile(os.path.join(BG_UPLOAD_DIR, fn))]
    items = [{"name": fn, "url": f"{public_base()}/background/uploads/{quote(fn)}"} for fn in sorted(files)]
    return jsonify({"status": "success", "items": items})

@app.route("/background/current", methods=["GET"])
def background_current():
    meta = get_bg_meta()
    mode = meta.get("mode")

    # 這個端點永遠不要被快取（避免「current」被記住）
    nocache_headers = {
        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
        "Pragma": "no-cache",
    }

    # 1) static：靜態圖在 Netlify，所以回「相對路徑」的 302
    if mode == "static" and meta.get("name"):
        resp = redirect(f"/static/{meta['name']}", code=302)  # <-- 關鍵：相對路徑，不要帶 Railway 網域
        for k, v in nocache_headers.items():
            resp.headers[k] = v
        return resp

    # 2) upload：檔在 Railway volume，直接送檔；仍附 no-store
    if mode == "upload" and meta.get("name"):
        path = os.path.join(BG_UPLOAD_DIR, meta["name"])
        if os.path.isfile(path):
            resp = make_response(send_from_directory(BG_UPLOAD_DIR, meta["name"]))
            for k, v in nocache_headers.items():
                resp.headers[k] = v
            return resp

    # 3) url：轉到外部 URL；仍附 no-store
    if mode == "url" and meta.get("url"):
        resp = redirect(meta["url"], code=302)
        for k, v in nocache_headers.items():
            resp.headers[k] = v
        return resp

    return "", 404


@app.route("/background/uploads/<path:filename>", methods=["GET"])
def background_uploads(filename):
    filename = os.path.basename(filename)
    path = os.path.join(BG_UPLOAD_DIR, filename)
    if os.path.isfile(path):
        resp = send_from_directory(BG_UPLOAD_DIR, filename)
        resp.headers["Cache-Control"] = "no-store, max-age=0"
        return resp
    return "", 404

# ====== Local run ======
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)

