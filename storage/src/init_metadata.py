from pymongo import MongoClient
import datetime

def init_metadata():
    client = MongoClient("mongodb://mongo.cyber.net:27017/")
    db = client["datalake"]
    collection = db["metadata_catalog"]

    # Pulizia catalogo esistente
    collection.delete_many({})

    metadata = [
        {
            "id": "ds_historical_nids",
            "name": "BigFlow-NIDS Historical Dataset",
            "description": "Dataset storico per il rilevamento delle intrusioni (NIDS). Contiene flussi di traffico etichettati (DDoS, Brute Force, ecc.) per il training e il benchmarking.",
            "source": "Ricerca Accademica / GitHub",
            "format": "Parquet / CSV",
            "location": "/opt/spark/data/processed/BigFlow-NIDS.parquet",
            "category": "Network Security",
            "created_at": datetime.datetime.now(),
            "schema": [
                {"name": "vettore_attacco", "type": "String", "description": "Tipologia di minaccia identificata"},
                {"name": "occorrenze", "type": "Long", "description": "Numero di flussi rilevati"},
                {"name": "traffico_h", "type": "String", "description": "Volume totale in formato leggibile"}
            ]
        },
        {
            "id": "ds_live_sniffer",
            "name": "Live Network Traffic (Sniffer)",
            "description": "Traffico di rete catturato in tempo reale dal fabric EVPN-VXLAN tramite il nodo sniffer.",
            "source": "Network Sniffer (kathara-sniffer)",
            "format": "PCAP",
            "location": "/catture/analisi_traffico.pcap",
            "category": "Live Monitoring",
            "created_at": datetime.datetime.now(),
            "schema": [
                {"name": "Tempo", "type": "Timestamp", "description": "Orario di cattura del pacchetto"},
                {"name": "Sorgente", "type": "IP Address", "description": "Indirizzo IP di origine"},
                {"name": "Destinazione", "type": "IP Address", "description": "Indirizzo IP di destinazione"},
                {"name": "Protocollo", "type": "String", "description": "Protocollo di rete (TCP/UDP/ARP)"}
            ]
        }
    ]

    collection.insert_many(metadata)
    print(f"Catalogo Metadati inizializzato con {len(metadata)} dataset.")

if __name__ == "__main__":
    init_metadata()
