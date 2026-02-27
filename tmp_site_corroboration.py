from pathlib import Path
from collections import Counter
import re

base = Path(r"c:/Users/dnathanson/OneDrive - NHP/dev/ev-charger-log-analyzer/examples/delta_ac_max")
chargers = {
    '216': 'KKB241600082WE',
    '187': 'KKB240500162WE',
    '189': 'KKB241600085WE',
}
critical_codes = {
    'EV0081','EV0082','EV0083','EV0084','EV0085','EV0086','EV0087','EV0088','EV0089','EV0090',
    'EV0091','EV0092','EV0093','EV0094','EV0095','EV0096','EV0097','EV0098','EV0099','EV0100',
    'EV0101','EV0110','EV0114','EV0115','EV0116'
}
code_re = re.compile(r'-((?:EV\d{4})|(?:1\d{4,}))$')

for short, serial in chargers.items():
    folder = next((path for path in base.iterdir() if path.is_dir() and serial in path.name), None)
    print(f"\n=== {short} ({serial}) ===")
    if not folder:
        print('folder not found')
        continue

    event_dir = folder / 'Storage' / 'EventLog'
    counts = Counter()
    for event_file in sorted(event_dir.glob('*_Events.csv')):
        try:
            for line in event_file.read_text(encoding='utf-8', errors='ignore').splitlines():
                line = line.strip()
                if not line:
                    continue
                match = code_re.search(line)
                if match:
                    code = match.group(1)
                    if code in critical_codes:
                        counts[code] += 1
        except Exception:
            pass

    sys_dir = folder / 'Storage' / 'SystemLog'
    ocp_count = 0
    backend_disconnect_count = 0
    for sys_file in sorted(sys_dir.glob('SystemLog*')):
        try:
            text = sys_file.read_text(encoding='utf-8', errors='ignore')
            ocp_count += len(re.findall(r'\[IntComm\]\s+AC output OCP(?!\s+recover)', text, flags=re.I))
            backend_disconnect_count += text.count('Backend connection fail')
        except Exception:
            pass

    ocpp_rejections = 0
    lost_tx_markers = 0
    for ocpp_file in sorted(sys_dir.glob('OCPP16J_Log.csv*')):
        try:
            text = ocpp_file.read_text(encoding='utf-8', errors='ignore')
            ocpp_rejections += len(re.findall(r'status\":\"Rejected\"|status:\"Rejected\"', text))
            lost_tx_markers += len(re.findall(r'transactionId"?\s*[:=]\s*-1', text))
        except Exception:
            pass

    print(f"Critical events total: {sum(counts.values())}")
    print(f"EV0082 (overcurrent): {counts.get('EV0082', 0)}")
    print(f"EV0085 (RCD): {counts.get('EV0085', 0)}")
    print(f"EV0091 (PWMP): {counts.get('EV0091', 0)}")
    print(f"EV0110 (internal comm): {counts.get('EV0110', 0)}")
    print(f"SystemLog IntComm AC output OCP: {ocp_count}")
    print(f"Backend connection fail count: {backend_disconnect_count}")
    print(f"OCPP Rejected responses (heuristic): {ocpp_rejections}")
    print(f"OCPP transactionId=-1 markers (heuristic): {lost_tx_markers}")
