# Kill-chain mo phong

| Buoc | Hanh dong cua attacker | Detection | Rule | Level | MITRE |
|------|------------------------|-----------|------|-------|-------|
| 1 | ping quet host song | Suricata ICMP | 100101 | 7 | T1018 |
| 2 | nmap -sS quet cong | Suricata SYN scan | 100102 | 10 | T1046 |
| 3 | hydra brute force SSH | Wazuh sshd + Suricata | 100110 | 12 | T1110.001 |
| 4 | SSH dang nhap thanh cong | Wazuh correlation | 100111 | 14 | T1078 |

## Vi sao tang 4 la quan trong nhat
Mot lan dang nhap thanh cong don le la binh thuong. Nhung dang nhap thanh
cong NGAY SAU mot chuoi brute force tu CUNG mot IP -> dau hieu chiem tai
khoan. Luat 100111 dung if_matched_sid + same_source_ip + timeframe de bat
dung tinh huong nay.
