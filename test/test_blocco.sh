#!/bin/bash
# test_blocco.sh
# Script per testare il blocco di un IP di test (es. 192.168.20.99)

TEST_IP=${1:-"192.168.20.2"}

echo "=========================================================="
echo "   DEMO: SIMULAZIONE ATTIVAZIONE REGOLA DI BLOCCO IP     "
echo "=========================================================="
echo "[*] IP bersaglio del blocco: $TEST_IP"

# Esegui l'invio del pacchetto di blocco
kathara exec admin -- python3 /shared/test_blocco.py $TEST_IP

echo -e "\n[*] Verifica delle regole applicate sul Gateway r5 (iptables)..."
kathara exec r5 -- iptables -S | grep $TEST_IP

echo -e "\n[+] Se vedi le regole REJECT con l'IP $TEST_IP, il test ha avuto successo!"
echo "=========================================================="
