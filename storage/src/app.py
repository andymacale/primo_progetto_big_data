import streamlit as st
from pymongo import MongoClient
import socket
import time
import datetime
from pyspark.sql import SparkSession
from pyspark import SparkContext
from functions import homepage
from functions import catalogo
from functions import spark_analysis
from functions import live_sniffer
from functions import ai_copilot

st.set_page_config(page_title="Dashboard Big Data - Admin", page_icon="📊", layout="wide")

st.title("Pannello Amministratore Datalake")
st.markdown(f"Applicazione in esecuzione sul nodo: `{socket.gethostname()}`")

@st.cache_resource
def get_mongo_client():
    return MongoClient("mongodb://mongo.cyber.net:27017/", serverSelectionTimeoutMS=5000)

m_client = get_mongo_client()
m_ok = True
try:
    m_client.server_info()
except:
    m_ok = False

if m_ok:
    try:
        ora_limite = time.time() - 300
        alert_recenti = list(m_client["datalake"]["alerts"].find({"timestamp": {"$gt": ora_limite}}).sort("timestamp", -1).limit(5))
        
        if alert_recenti:
            blocked = list(m_client["datalake"]["blocked_ips"].find())
            blocked_ips = set(b['ip'] for b in blocked)
            
            for a in alert_recenti[:1]:
                if a['source'] in blocked_ips:
                    st.warning(f" **ATTACCO MITIGATO** — IP `{a['source']}` bloccato .\n\n{a['message']}")
                else:
                    st.error(f" **ATTACCO IN CORSO!** — {a['message']}")
    except:
        pass

def force_spark_reset():
    st.cache_resource.clear()

@st.cache_resource
def get_spark_session():
    jars = [
        "/app/jars/mongo-spark-connector_2.12-10.3.0.jar",
        "/app/jars/mongodb-driver-sync-4.11.1.jar",
        "/app/jars/mongodb-driver-core-4.11.1.jar",
        "/app/jars/bson-4.11.1.jar",
        "/app/jars/bson-record-codec-4.11.1.jar"
    ]
    
    spark = SparkSession.builder \
        .appName("NIDS-Dashboard") \
        .master("spark://spark-master:7077") \
        .config("spark.driver.host", "10.0.0.2") \
        .config("spark.driver.bindAddress", "0.0.0.0") \
        .config("spark.mongodb.read.connection.uri", "mongodb://mongo.cyber.net:27017/datalake.traffico_nids") \
        .config("spark.mongodb.write.connection.uri", "mongodb://mongo.cyber.net:27017/datalake.alerts") \
        .config("spark.jars", ",".join(jars)) \
        .getOrCreate()
        
    return spark

with st.sidebar:
    st.header("Pannello di controllo")
    auto_refresh = st.checkbox("Auto-refresh Live (2s)", value=False)
    if auto_refresh:
        time.sleep(2)
        st.rerun()
    
    st.header("Gestione Sessioni")
    if st.button("Hard Reset Spark"):
        force_spark_reset()
        st.rerun()
    
    masking = st.toggle("Privacy Mode", False)

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

def block_ip(ip_address):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.sendto(f"BLOCK:{ip_address}".encode("utf-8"), ("10.0.0.1", 5000))
        sock.close()

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
        log_action("NIDS", "BlockIP", f"IP {ip_address} aggiunto alla blocklist e bloccato su r5")
        return True
    except Exception as e:
        log_action("NIDS", "BlockIP-FAILED", f"Errore: {str(e)}")
        return False

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "Homepage", 
    "Catalogo", 
    "Analisi", 
    "Sniffer", 
    "Assistente IA"
])

with tab1:
    homepage.render_homepage(m_client, m_ok, get_spark_session, force_spark_reset)

with tab2:
    catalogo.render_catalogo(m_client, m_ok, get_spark_session)

with tab3:
    spark_analysis.render_spark_analysis(m_client, m_ok, get_spark_session, force_spark_reset, block_ip, log_action)

with tab4:
    live_sniffer.render_live_sniffer(m_client, masking)

with tab5:
    ai_copilot.render_ai_copilot(m_client, m_ok, log_action, get_spark_session)