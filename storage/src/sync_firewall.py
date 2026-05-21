#!/usr/bin/env python3
import socket
import time
from pymongo import MongoClient

print("[*] Sincronizzazione regole Firewall da MongoDB al Gateway r5...")

try:
    client = MongoClient("mongodb://mongo.cyber.net:27017/", serverSelectionTimeoutMS=5000)
    db = client["datalake"]
    
    blocked_ips = list(db["blocked_ips"].find({"status": "BLOCKED"}))
    
    if len(blocked_ips) > 0:
        print(f"[!] Trovati {len(blocked_ips)} IP da sincronizzare.")
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        
        for record in blocked_ips:
            ip = record["ip"]
            sock.sendto(f"BLOCK:{ip}".encode("utf-8"), ("10.0.0.1", 5000))
            print(f"[+] Regola ripristinata per l'IP: {ip}")
            time.sleep(0.1) 
            
        sock.close()
    else:
        print("[-] Nessun IP bloccato presente nel database.")
        
    print("[*] Sincronizzazione completata con successo.")
except Exception as e:
    print(f"[X] Errore durante la sincronizzazione: {e}")
