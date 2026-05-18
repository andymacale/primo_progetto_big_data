import time
import os
from scapy.all import rdpcap, IP, TCP, UDP, ARP
from pymongo import MongoClient

def ingest_pcap():
    pcap_path = "/catture/analisi_traffico.pcap"
    client = MongoClient("mongodb://mongo.cyber.net:27017/")
    db = client["datalake"]
    collection = db["live_traffic"]
    
    print(f"Ingestore PCAP avviato. Monitoraggio di {pcap_path}...")
    
    last_processed_count = 0
    
    while True:
        if os.path.exists(pcap_path):
            try:
                try:
                    packets = rdpcap(pcap_path)
                except Exception:
                    time.sleep(1)
                    continue
                current_count = len(packets)
                
                if current_count > last_processed_count:
                    # Prendi solo i nuovi pacchetti
                    new_packets = packets[last_processed_count:]
                    to_insert = []
                    
                    for p in new_packets:
                        pkt_doc = {
                            "timestamp": float(p.time),
                            "summary": p.summary(),
                            "length": len(p)
                        }
                        
                        if IP in p:
                            pkt_doc["src"] = p[IP].src
                            pkt_doc["dst"] = p[IP].dst
                            pkt_doc["proto"] = "TCP" if TCP in p else ("UDP" if UDP in p else "IP")
                        elif ARP in p:
                            pkt_doc["src"] = p[ARP].psrc
                            pkt_doc["dst"] = p[ARP].pdst
                            pkt_doc["proto"] = "ARP"
                        else:
                            pkt_doc["src"] = "Layer 2"
                            pkt_doc["dst"] = "Broadcast"
                            pkt_doc["proto"] = "Ether"

                        to_insert.append(pkt_doc)
                    
                    if to_insert:
                        collection.insert_many(to_insert)
                        
                        # --- LOGICA DI RILEVAMENTO ALERT LIVE ---
                        alert_coll = db["alerts"]
                        
                        # Carica la blocklist corrente
                        blocked_ips = set(b['ip'] for b in db["blocked_ips"].find())
                        
                        for p in to_insert:
                            alert_msg = None
                            attacker_ip = None
                            
                            if p.get("proto") == "TCP":
                                summary = p.get("summary", "").lower()
                                src_ip = p.get("src", "???")
                                dst_ip = p.get("dst", "???")
                                
                                # Cerchiamo pacchetti DIRETTI verso porte critiche
                                # Formato: "src_ip:src_port > dst_ip:dst_port flags"
                                # Se la DESTINAZIONE contiene :ftp/:bgp/:ssh, l'attaccante è il SRC
                                
                                # Splittiamo il summary per trovare la destinazione
                                if " > " in summary:
                                    parte_dst = summary.split(" > ")[1]  # "2.0.0.131:ftp s / padding"
                                    
                                    if ":bgp" in parte_dst or ":179" in parte_dst:
                                        alert_msg = f"POSSIBILE BGP HIJACKING: Tentativo di connessione alla porta 179 del nodo {dst_ip}"
                                        attacker_ip = src_ip
                                    elif ":ftp" in parte_dst or ":21" in parte_dst:
                                        alert_msg = f"TENTATIVO FILE INJECTION: Tentativo FTP verso {dst_ip}"
                                        attacker_ip = src_ip
                                    elif ":ssh" in parte_dst or ":22" in parte_dst:
                                        alert_msg = f"TENTATIVO BRUTE FORCE SSH: Tentativo SSH verso {dst_ip}"
                                        attacker_ip = src_ip
                            
                            if alert_msg and attacker_ip:
                                is_blocked = attacker_ip in blocked_ips
                                alert_coll.insert_one({
                                    "timestamp": p["timestamp"],
                                    "message": alert_msg,
                                    "severity": "INFO" if is_blocked else "CRITICAL",
                                    "source": attacker_ip,
                                    "target": p.get("dst", "???"),
                                    "status": "MITIGATED" if is_blocked else "ACTIVE"
                                })
                                if is_blocked:
                                    print(f"MITIGATO: Attacco da {attacker_ip} bloccato a livello di rete, registrato per tracciabilità.")
                                else:
                                    print(f"ALERT: {alert_msg} [Attaccante: {attacker_ip}]")

                        print(f"Inseriti {len(to_insert)} nuovi pacchetti su MongoDB.")
                    
                    last_processed_count = current_count
                
            except Exception as e:
                print(f"Errore durante l'ingestione: {e}")
        
        time.sleep(1)

if __name__ == "__main__":
    ingest_pcap()
