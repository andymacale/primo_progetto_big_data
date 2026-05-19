from pymongo import MongoClient

def clear_db():
    print("[*] Connessione a MongoDB...")
    client = MongoClient("mongodb://mongo.cyber.net:27017/", serverSelectionTimeoutMS=5000)
    db = client["datalake"]
    
    # Rimuovi tutti gli IP bloccati
    res_ips = db["blocked_ips"].delete_many({})
    # Rimuovi tutti gli allarmi di sicurezza generati
    res_alerts = db["alerts"].delete_many({})
    
    print(f"[+] Pulizia completata.")
    print(f"    - IP Bloccati rimossi: {res_ips.deleted_count}")
    print(f"    - Allarmi di sicurezza rimossi: {res_alerts.deleted_count}")

if __name__ == "__main__":
    clear_db()
