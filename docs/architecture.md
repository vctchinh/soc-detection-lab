flowchart LR
	Kali["Kali Attacker<br>192.168.56.30"] -->|tan cong| Victim["Victim Ubuntu<br>192.168.56.20"]
	Victim -->|Suricata eve.json| Agent["Wazuh Agent"]
	Agent -->|cong 1514 va 1515| Mgr["Wazuh Manager - analysisd + rules"]
	Mgr --> Idx["Wazuh Indexer"]
	Idx --> Dash["Dashboard<br>Threat Hunting + MITRE"]


Luồng xử lý một sự kiện
1. Suricata sinh alert → ghi `eve.json`
2. Wazuh agent đọc `eve.json` → gửi về manager (cổng 1514/1515)
3. `analysisd`: decoder → rule (custom `100101..100111`) → gắn level + MITRE
4. Indexer lưu → Dashboard trực quan hóa
