#!/bin/bash
# sblocca_tutti.sh
# Script per sbloccare tutti gli IP (svuota database MongoDB e regole iptables su r5)

echo "=========================================================="
echo "   SBLOCCO COMPLETO FIREWALL E DATALAKE METADATA          "
echo "=========================================================="

echo "[*] 1. Ripulitura database MongoDB..."
kathara exec admin -- python3 /shared/query.py

echo -e "\n[*] 2. Flashing delle regole iptables su Gateway r5..."
kathara exec r5 -- iptables -F FORWARD
kathara exec r5 -- iptables -F INPUT

echo -e "\n[+] Sblocco completato! Stato attuale iptables su r5:"
kathara exec r5 -- iptables -L FORWARD -n

echo "=========================================================="
