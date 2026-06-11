#!/bin/bash
# Resetta lo stato della simulazione NIDS per poterla rilanciare da capo.
# Uso: ./reset_test.sh

set -e
cd "$(dirname "$0")"

echo "[1/3] Pulizia MongoDB (blocked_ips + alerts)..."
kathara exec admin -- python3 -c "
from pymongo import MongoClient
db = MongoClient('mongodb://mongo.cyber.net:27017/')['datalake']
r1 = db['blocked_ips'].delete_many({})
r2 = db['alerts'].delete_many({})
print(f'  blocked_ips rimossi: {r1.deleted_count}')
print(f'  alerts rimossi: {r2.deleted_count}')
"

echo "[2/3] Reset firewall su r5..."
kathara exec r5 -- iptables -F FORWARD
kathara exec r5 -- iptables -F INPUT
echo "  iptables pulito"

echo "[3/3] Riavvio pcap_ingestor..."
kathara exec admin -- bash -c "pkill -f pcap_ingestor 2>/dev/null; nohup python3 /app/pcap_ingestor.py > /var/log/pcap_ingestor.log 2>&1 &"
sleep 2
kathara exec admin -- bash -c "pgrep -f pcap_ingestor > /dev/null && echo '  pcap_ingestor avviato' || echo '  ERRORE: pcap_ingestor non partito'"

echo ""
echo "Reset completato. Lancia ./avvia_attacco.sh per simulare l'attacco."
