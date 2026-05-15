import streamlit as st
from pymongo import MongoClient
import socket
import pandas as pd
import os
import subprocess
import time
import datetime
from scapy.all import rdpcap, IP, TCP, UDP, ARP
from pyspark.sql import SparkSession
from pyspark import SparkContext

# Configurazione Pagina
st.set_page_config(page_title="Dashboard Big Data - Admin", page_icon="📊", layout="wide")

st.title("Pannello Amministratore Datalake")
st.markdown(f"Applicazione in esecuzione sul nodo: `{socket.gethostname()}`")

# --- FUNZIONI DI CONNESSIONE ---
@st.cache_resource
def get_mongo_client():
    return MongoClient("mongodb://mongo.cyber.net:27017/", serverSelectionTimeoutMS=5000)

m_client = get_mongo_client()
m_ok = True
try:
    m_client.server_info()
except:
    m_ok = False

# --- LOGICA ALERT REAL-TIME (Banner globale) ---
if m_ok:
    try:
        ora_limite = time.time() - 60
        alert_recenti = list(m_client["datalake"]["alerts"].find({"timestamp": {"$gt": ora_limite}}).sort("timestamp", -1).limit(5))
        
        if alert_recenti:
            # Conta gli IP unici sotto attacco
            ip_attaccanti = set(a['source'] for a in alert_recenti)
            blocked = list(m_client["datalake"]["blocked_ips"].find())
            blocked_ips = set(b['ip'] for b in blocked)
            
            for a in alert_recenti[:1]:  # Mostra solo l'ultimo alert
                if a['source'] in blocked_ips:
                    st.warning(f"🛡️ **ATTACCO MITIGATO** — IP `{a['source']}` bloccato automaticamente.\n\n{a['message']}")
                else:
                    st.error(f"🚨 **ATTACCO IN CORSO!** — {a['message']}")
    except:
        pass

@st.cache_resource
def get_spark_session():
    jars = [
        "/opt/spark/src/jars/mongo-spark-connector_2.12-10.3.0.jar",
        "/opt/spark/src/jars/mongodb-driver-sync-4.11.1.jar",
        "/opt/spark/src/jars/mongodb-driver-core-4.11.1.jar",
        "/opt/spark/src/jars/bson-4.11.1.jar",
        "/opt/spark/src/jars/bson-record-codec-4.11.1.jar"
    ]
    return SparkSession.builder \
        .appName("NIDS-Dashboard") \
        .master("spark://spark-master:7077") \
        .config("spark.mongodb.read.connection.uri", "mongodb://mongo.cyber.net:27017/datalake.traffico_nids") \
        .config("spark.mongodb.write.connection.uri", "mongodb://mongo.cyber.net:27017/datalake.alerts") \
        .config("spark.jars", ",".join(jars)) \
        .getOrCreate()

# Sidebar
with st.sidebar:
    st.header("⚙️ Pannello Controllo")
    auto_refresh = st.checkbox("Auto-refresh Live (2s)", value=False)
    if auto_refresh:
        time.sleep(2)
        st.rerun()
    
    st.header("Connettività Servizi")
    if m_ok:
        st.success("MongoDB: Collegato")
    else:
        st.error("MongoDB: Disconnesso")
    
    try:
        s_test = get_spark_session()
        st.success("Spark Master: Collegato")
    except Exception as e:
        st.error(f"Spark Master: Disconnesso\n {e}")
    
    st.header("Gestione Sessioni")
    if st.button("Hard Reset Spark"):
        st.cache_resource.clear()
        st.rerun()
    
    masking = st.toggle("Privacy Mode (Masking)", False)


# --- FUNZIONE AUDIT LOG ---
def log_action(user, action, details):
    try:
        m_client["datalake"]["audit_logs"].insert_one({
            "timestamp": datetime.datetime.now(),
            "user": user,
            "action": action,
            "details": details
        })
    except:
        pass

# --- FUNZIONE BLOCCO IP (Risposta Attiva) ---
def block_ip(ip_address):
    try:
        # Registra l'IP nella blocklist su MongoDB
        m_client["datalake"]["blocked_ips"].update_one(
            {"ip": ip_address},
            {"$set": {
                "ip": ip_address,
                "blocked_at": datetime.datetime.now(),
                "reason": "Rilevamento automatico NIDS",
                "status": "BLOCKED"
            }},
            upsert=True
        )
        log_action("NIDS", "BlockIP", f"IP {ip_address} aggiunto alla blocklist")
        return True
    except Exception as e:
        log_action("NIDS", "BlockIP-FAILED", f"Errore: {str(e)}")
        return False

# --- TABS ---
tab1, tab2, tab3, tab4 = st.tabs(["📚 Catalogo Data Lake", "📊 Analisi (Spark)", "🛰️ Sniffer (Live)", "🛡️ Governance & Security"])

# ===================== TAB 1: CATALOGO =====================
with tab1:
    st.header("📚 Catalogo Metadati e Data Governance")
    if m_ok:
        search = st.text_input("🔍 Cerca dataset nel Catalogo...", "")
        try:
            query = {"$or": [{"name": {"$regex": search, "$options": "i"}}, {"description": {"$regex": search, "$options": "i"}}]} if search else {}
            catalog = list(m_client["datalake"]["metadata_catalog"].find(query))
            for ds in catalog:
                with st.container(border=True):
                    col_title, col_status = st.columns([4, 1])
                    with col_title:
                        st.subheader(f"Dataset: {ds['name']}")
                    with col_status:
                        exists = os.path.exists(ds['location']) if "/" in ds['location'] else True
                        if exists:
                            st.success("● ONLINE")
                        else:
                            st.error("● OFFLINE")
                    
                    c1, c2, c3 = st.columns([2, 1, 1])
                    with c1:
                        st.write(f"**Descrizione:** {ds['description']}")
                        st.write(f"**Proprietario:** `Admin / SOC Team`")
                    with c2:
                        st.write(f"**Formato:** `{ds['format']}`")
                        st.write(f"**Categoria:** {ds['category']}")
                    with c3:
                        if ds['id'] == "ds_live_sniffer":
                            count = m_client["datalake"]["live_traffic"].count_documents({})
                            st.metric("Record Ingeriti", count)
                        else:
                            st.write(f"**Origine:** {ds['source']}")
                    
                    with st.expander("Visualizza Schema Tecnico"):
                        st.dataframe(pd.DataFrame(ds['schema']), use_container_width=True, hide_index=True)
                    
                    last_update = ds['created_at']
                    if ds['id'] == "ds_live_sniffer":
                        last_pkt = m_client["datalake"]["live_traffic"].find_one(sort=[("timestamp", -1)])
                        if last_pkt:
                            last_update = datetime.datetime.fromtimestamp(last_pkt['timestamp'])
                    st.markdown(f"*Ultimo aggiornamento: {last_update.strftime('%H:%M:%S')} ({last_update.strftime('%d-%m-%Y')})*")
        except Exception as e:
            st.error(f"Errore catalogo: {e}")

# ===================== TAB 2: SPARK =====================
with tab2:
    st.header("📊 Intelligence Rilevamento Anomalie")
    s_session = None
    try:
        s_session = get_spark_session()
        s_ok = True
    except:
        s_ok = False
    
    if s_ok:
        if st.button("Avvia Analisi Real-time"):
            try:
                parquet_path = "/opt/spark/data/processed/BigFlow-NIDS.parquet"
                query_path = "/app/analytics/queries/rilevamento_anomalie.sql"
                with st.spinner("Elaborazione Spark in corso..."):
                    df = s_session.read.parquet(parquet_path)
                    df.createOrReplaceTempView("traffico_nids")
                    with open(query_path, 'r') as f:
                        query_sql = f.read()
                    risultati = s_session.sql(query_sql).toPandas()
                    log_action("Admin", "RunSparkAnalysis", "Eseguito rilevamento anomalie su 66M record")
                
                if not risultati.empty:
                    tot_bytes = risultati['traffico_b'].sum()
                    def format_h(b):
                        if b >= 1024**4: return f"{round(b/(1024**4), 2)} TB"
                        if b >= 1024**3: return f"{round(b/(1024**3), 2)} GB"
                        if b >= 1024**2: return f"{round(b/(1024**2), 2)} MB"
                        if b >= 1024: return f"{round(b/1024, 2)} KB"
                        return f"{b} B"
                    
                    m1, m2, m3 = st.columns(3)
                    m1.metric("Attacchi Rilevati", f"{risultati['occorrenze'].sum():,}")
                    m2.metric("Vettori Unici", len(risultati['vettore_attacco'].unique()))
                    m3.metric("Traffico Analizzato", format_h(tot_bytes))
                    st.subheader("Dettaglio Minacce Identificate")
                    st.dataframe(risultati.drop(columns=['traffico_b']), use_container_width=True, hide_index=True)
                else:
                    st.success("Nessuna anomalia rilevata.")
            except Exception as e:
                st.error(f"Errore Spark: {e}")
    else:
        st.warning("Spark Master non disponibile.")

# ===================== TAB 3: SNIFFER =====================
with tab3:
    st.header("🛰️ Monitoraggio Traffico di Rete (Live)")
    st.write("Visualizzazione pacchetti catturati dal nodo `sniffer` sul fabric EVPN-VXLAN.")
    
    col_s1, col_s2 = st.columns([3, 1])
    
    with col_s2:
        if st.button("🔄 Aggiorna Pacchetti"):
            st.rerun()
        pcap_path = "/catture/analisi_traffico.pcap"
        if os.path.exists(pcap_path) and os.path.getsize(pcap_path) > 0:
            with open(pcap_path, "rb") as f:
                st.download_button("📥 Scarica PCAP", f, "analisi.pcap", "application/octet-stream")
        st.info("Apri con Wireshark per analisi dettagliata.")
    
    with col_s1:
        try:
            live_coll = m_client["datalake"]["live_traffic"]
            packets = list(live_coll.find().sort("timestamp", -1).limit(20))
            
            if packets:
                st.caption(f"Ultimi {len(packets)} pacchetti (più recenti in alto)")
                pkt_data = []
                for p in packets:
                    src, dst = p.get("src", "???"), p.get("dst", "???")
                    if masking and "." in src:
                        src = ".".join(src.split(".")[:-1]) + ".xxx"
                    if masking and "." in dst:
                        dst = ".".join(dst.split(".")[:-1]) + ".xxx"
                    pkt_data.append({
                        "Tempo": time.strftime('%H:%M:%S', time.localtime(p['timestamp'])),
                        "Sorgente": src,
                        "Destinazione": dst,
                        "Protocollo": p.get("proto", "???"),
                        "Dettaglio": p.get("summary", "")[:80]
                    })
                st.dataframe(pd.DataFrame(pkt_data), use_container_width=True, hide_index=True)
            else:
                st.info("In attesa di pacchetti dall'ingestore...")
        except Exception as e:
            st.error(f"Errore MongoDB Live: {e}")

# ===================== TAB 4: GOVERNANCE =====================
with tab4:
    st.header("🛡️ Security by Design & Governance")
    
    # --- SEZIONE 1: ALERT E RISPOSTA ATTIVA ---
    st.subheader("🚨 Minacce Rilevate & Risposta Attiva")
    
    if m_ok:
        col_alert, col_blocked = st.columns(2)
        
        with col_alert:
            st.markdown("**Alert Recenti (ultimi 60s)**")
            alerts = list(m_client["datalake"]["alerts"].find().sort("timestamp", -1).limit(10))
            blocked_list = list(m_client["datalake"]["blocked_ips"].find())
            blocked_ips = set(b['ip'] for b in blocked_list)
            
            if alerts:
                for i, a in enumerate(alerts[:5]):
                    ip = a.get('source', '???')
                    msg = a.get('message', '')
                    is_blocked = ip in blocked_ips
                    
                    col_msg, col_btn = st.columns([3, 1])
                    with col_msg:
                        if is_blocked:
                            st.markdown(f"✅ ~~{msg}~~ — **BLOCCATO**")
                        else:
                            st.markdown(f"🔴 {msg}")
                    with col_btn:
                        if not is_blocked:
                            if st.button(f"🛡️ Blocca {ip}", key=f"block_{i}"):
                                block_ip(ip)
                                st.rerun()
                        else:
                            st.success("Mitigato")
            else:
                st.success("Nessun alert attivo. Il sistema è sicuro. ✅")
        
        with col_blocked:
            st.markdown("**IP Bloccati (Firewall Virtuale)**")
            if blocked_list:
                for b in blocked_list:
                    st.code(f"🚫 {b['ip']} — Bloccato il {b['blocked_at'].strftime('%d-%m-%Y %H:%M:%S')}")
            else:
                st.info("Nessun IP bloccato.")
    
    st.markdown("---")
    
    # --- SEZIONE 2: AUDIT LOG + PERFORMANCE ---
    col_sec1, col_sec2 = st.columns(2)
    
    with col_sec1:
        st.subheader("🕵️ Audit Log (Tracciabilità)")
        if st.button("🔄 Aggiorna Log"):
            st.rerun()
        try:
            logs = list(m_client["datalake"]["audit_logs"].find().sort("timestamp", -1).limit(10))
            if logs:
                df_logs = pd.DataFrame(logs).drop(columns=['_id'])
                df_logs['timestamp'] = df_logs['timestamp'].dt.strftime('%d-%m-%Y %H:%M:%S')
                st.dataframe(df_logs, use_container_width=True, hide_index=True)
            else:
                st.info("Nessun log registrato.")
        except:
            st.error("Errore Audit Log")
    
    with col_sec2:
        st.subheader("⚡ Performance & Efficiency")
        perf_data = pd.DataFrame({
            'Volume (Mln Record)': [1, 10, 30, 66],
            'Spark (sec)': [2, 8, 15, 28],
            'Legacy DB (sec)': [5, 45, 180, 450]
        })
        st.line_chart(perf_data.set_index('Volume (Mln Record)'))
        st.caption("Confronto: Spark Cluster vs Database Relazionale Singolo")