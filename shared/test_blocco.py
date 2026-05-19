import socket
import sys

def send_block_command(ip_to_block):
    print(f"[*] Invio comando di blocco per IP: {ip_to_block} al Gateway r5...")
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.sendto(f"BLOCK:{ip_to_block}".encode("utf-8"), ("10.0.0.1", 5000))
    sock.close()
    print("[+] Comando inviato con successo.")

if __name__ == "__main__":
    ip = sys.argv[1] if len(sys.argv) > 1 else "192.168.20.99"
    send_block_command(ip)
