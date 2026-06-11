#!/bin/bash
# Lancia un SYN Flood dal nodo attacker verso il web server (2.0.0.131:80).
# Il pcap_ingestor rileverà l'attacco e genererà alert nella dashboard.
# Uso: ./avvia_attacco.sh

cd "$(dirname "$0")"

echo "Lancio SYN Flood su 2.0.0.131:80 (200 pacchetti)..."
kathara exec attacker -- hping3 -S -p 80 -c 200 -i u500 2.0.0.131
echo ""
echo "Attacco completato. Controlla la dashboard: dovrebbe comparire 'ATTACCO IN CORSO!'."
echo "Vai su Analisi -> Sicurezza per bloccare l'IP 192.168.20.2."
