import time
import os
from scapy.all import rdpcap, IP, TCP, UDP, ARP
from pymongo import MongoClient

def ingest_pcap():
    pcap_path = "/catture/analisi_traffico.pcap"
    client = MongoClient("mongodb://mongo.cyber.net:27017/")
    db = client["datalake"]
    
    try:
        if "live_traffic" not in db.list_collection_names():
            db.create_collection("live_traffic", capped=True, size=10 * 1024 * 1024, max=5000)
            print("Collezione 'live_traffic' creata come Capped Collection (limite 5000 pacchetti).")
        else:
            db.command("convertToCapped", "live_traffic", size=10 * 1024 * 1024, max=5000)
            print("Collezione 'live_traffic' convertita con successo in Capped Collection (limite 5000 pacchetti).")
    except Exception as ec:
        print(f"Nota su Capped Collection: {ec}")
        
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
                
                if current_count < last_processed_count:
                    last_processed_count = 0
                    print("Rilevata sovrascrittura/rotazione del file PCAP. Contatore resettato.")
                
                if current_count > last_processed_count:
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
                        
                        alert_coll = db["alerts"]
                        blocked_ips = set(b['ip'] for b in db["blocked_ips"].find())
                        
                        for p in to_insert:
                            alert_msg = None
                            attacker_ip = None
                            
                            if p.get("proto") == "TCP":
                                summary = p.get("summary", "").lower()
                                src_ip = p.get("src", "???")
                                dst_ip = p.get("dst", "???")
                                
                                if " > " in summary:
                                    parte_dst = summary.split(" > ")[1] 
                                    
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
