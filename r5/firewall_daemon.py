#!/usr/bin/env python3
import socket
import subprocess

UDP_IP = "0.0.0.0"
UDP_PORT = 5000

print(f"[*] Avvio Datacenter Firewall Daemon su UDP {UDP_PORT}...")
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind((UDP_IP, UDP_PORT))

while True:
    try:
        data, addr = sock.recvfrom(1024)
        msg = data.decode("utf-8").strip()
        
        if msg.startswith("BLOCK:"):
            target_ip = msg.split(":")[1]
            print(f"[!] Ricevuto comando di blocco per l'IP a livello di rete: {target_ip}")
            
            cmd_forward = [
                "iptables", "-A", "FORWARD", 
                "-s", target_ip, 
                "-j", "REJECT", 
                "--reject-with", "icmp-port-unreachable"
            ]
            
            cmd_input = [
                "iptables", "-A", "INPUT", 
                "-s", target_ip, 
                "-j", "REJECT", 
                "--reject-with", "icmp-port-unreachable"
            ]
            
            res_f = subprocess.run(cmd_forward, capture_output=True, text=True)
            res_i = subprocess.run(cmd_input, capture_output=True, text=True)
            
            if res_f.returncode == 0 and res_i.returncode == 0:
                print(f"[+] Regole FORWARD e INPUT applicate con successo su {target_ip}")
            else:
                print(f"[-] Errore nell'applicazione delle regole: F:{res_f.stderr} I:{res_i.stderr}")
                
    except Exception as e:
        print(f"[-] Errore nel demone firewall: {e}")
