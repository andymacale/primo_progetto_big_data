import streamlit as st
from pymongo import MongoClient
from pyspark.sql import SparkSession
import socket
import pandas as pd

# Configurazione Pagina
st.set_page_config(page_title="Dashboard Big Data - Admin", page_icon="📊", layout="wide")

st.title("Pannello Amministratore Datalake")
st.markdown(f"Applicazione in esecuzione sul nodo: `{socket.gethostname()}`")

# Sidebar per lo stato della rete
st.sidebar.header("Connettività Servizi")

# --- FUNZIONI DI CONNESSIONE ---

@st.cache_resource
def get_mongo_client():
    return MongoClient("mongodb://mongo.cyber.net:27017/", serverSelectionTimeoutMS=5000)

@st.cache_resource
def get_spark_session():
    # Carica i JAR dei connettori MongoDB dalla cartella condivisa
    jars = [
        "/opt/spark/src/jars/mongo-spark-connector_2.12-10.3.0.jar",
        "/opt/spark/src/jars/mongodb-driver-sync-4.11.1.jar",
        "/opt/spark/src/jars/mongodb-driver-core-4.11.1.jar",
        "/opt/spark/src/jars/bson-4.11.1.jar",
        "/opt/spark/src/jars/bson-record-codec-4.11.1.jar"
    ]
    return SparkSession.builder \
        .appName("StreamlitAdmin") \
        .master("spark://spark.cyber.net:7077") \
        .config("spark.jars", ",".join(jars)) \
        .getOrCreate()

def test_mongo():
    try:
        client = get_mongo_client()
        client.server_info() 
        return True, client
    except Exception as e:
        return False, str(e)

def test_spark():
    try:
        spark = get_spark_session()
        if spark.sparkContext._jsc.sc().isStopped():
            st.cache_resource.clear() 
            spark = get_spark_session()
        return True, spark
    except Exception as e:
        return False, str(e)


m_ok, m_client = test_mongo()
s_ok, s_session = test_spark()

if m_ok:
    st.sidebar.success("MongoDB: Collegato")
else:
    st.sidebar.error(f"MongoDB: Non raggiungibile\n({m_client})")

if s_ok:
    st.sidebar.success("Spark Master: Collegato")
else:
    st.sidebar.error(f"Spark: Non raggiungibile\n({s_session})")

tab1, tab2 = st.tabs(["Database (MongoDB)", "Analisi (Spark)"])

with tab1:
    st.header("Esplorazione Dati MongoDB")
    if m_ok:
        dbs = m_client.list_database_names()
        db_scelto = st.selectbox("Seleziona Database", dbs)
        
        if db_scelto:
            colls = m_client[db_scelto].list_collection_names()
            coll_scelta = st.selectbox("Seleziona Collezione", colls)
            
            if coll_scelta:
                data = list(m_client[db_scelto][coll_scelta].find().limit(10))
                if data:
                    st.dataframe(pd.DataFrame(data))
                else:
                    st.info("La collezione è vuota.")
    else:
        st.warning("Configura MongoDB per visualizzare i dati.")

with tab2:
    st.header("Intelligence Rilevamento Anomalie")
    if s_ok:
        col1, col2 = st.columns([3, 1])
        
        with col2:
            st.info("Cluster Spark operativo. Pronto per l'elaborazione distribuita.")
            if st.button("Avvia Analisi Real-time", use_container_width=True):
                st.cache_resource.clear()
        
        with col1:
            try:
                
                parquet_path = "/opt/spark/data/processed/BigFlow-NIDS.parquet"
                query_path = "/app/analytics/queries/rilevamento_anomalie.sql"

                with st.spinner("Elaborazione dati in corso sul cluster Spark..."):
                    df = s_session.read.parquet(parquet_path)
                    df.createOrReplaceTempView("traffico_nids")
                    
                    with open(query_path, 'r') as f:
                        query_sql = f.read()
                    
                    risultati = s_session.sql(query_sql).toPandas()
                
                # 2. Visualizzazione Metriche
                if not risultati.empty:
                    m1, m2, m3 = st.columns(3)
                    m1.metric("Attacchi Rilevati", f"{risultati['occorrenze'].sum():,}")
                    m2.metric("Vettori Unici", len(risultati['vettore_attacco'].unique()))
                    m3.metric("Traffico Analizzato", risultati['traffico_h'].iloc[0])
                    
                    st.subheader("Dettaglio Minacce Identificate")
                    st.dataframe(risultati, use_container_width=True, hide_index=True)
                    
                else:
                    st.success("Nessuna anomalia rilevata nel traffico recente.")
                    
            except Exception as e:
                st.error(f"Errore durante l'analisi: {str(e)}")
                st.info("Esegui lo script `bash ./ambiente_sviluppo/bin/run_analytics.sh` per generare i dati Parquet.")
    else:
        st.warning("Spark Master non disponibile. Impossibile avviare il motore di analisi.")