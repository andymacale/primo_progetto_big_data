import streamlit as st
from pymongo import MongoClient
from pyspark.sql import SparkSession
import socket
import pandas as pd

# Configurazione Pagina
st.set_page_config(page_title="Dashboard Big Data - Admin", page_icon="📊", layout="wide")

st.title("📊 Pannello Amministratore Datalake")
st.markdown(f"Applicazione in esecuzione sul nodo: `{socket.gethostname()}`")

# Sidebar per lo stato della rete
st.sidebar.header("Connettività Servizi")

# --- FUNZIONI DI CONNESSIONE ---

def test_mongo():
    try:
        # Punta al DNS configurato: 2.0.0.226
        client = MongoClient("mongodb://mongo.cyber.net:27017/", serverSelectionTimeoutMS=2000)
        client.server_info() 
        return True, client
    except Exception as e:
        return False, str(e)

def test_spark():
    try:
        # Punta al Master Spark: 2.0.0.194 porta 7077
        spark = SparkSession.builder \
            .appName("StreamlitAdmin") \
            .master("spark://spark.cyber.net:7077") \
            .getOrCreate()
        return True, spark
    except Exception as e:
        return False, str(e)

# --- VERIFICA STATO ---

m_ok, m_client = test_mongo()
s_ok, s_session = test_spark()

if m_ok:
    st.sidebar.success("✅ MongoDB: Collegato")
else:
    st.sidebar.error(f"❌ MongoDB: Non raggiungibile\n({m_client})")

if s_ok:
    st.sidebar.success("✅ Spark Master: Collegato")
else:
    st.sidebar.error(f"❌ Spark: Non raggiungibile\n({s_session})")

# --- INTERFACCIA PRINCIPALE ---

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
                # Mostra i dati reali dal DB
                data = list(m_client[db_scelto][coll_scelta].find().limit(10))
                if data:
                    st.dataframe(pd.DataFrame(data))
                else:
                    st.info("La collezione è vuota.")
    else:
        st.warning("Configura MongoDB per visualizzare i dati.")

with tab2:
    st.header("Big Data Processing con Spark")
    if s_ok:
        st.write("Configurazione Cluster:")
        st.json(s_session.sparkContext.getConf().getAll())
        
        if st.button("Lancia Test Job (Calcolo Pi Greco)"):
            import random
            num_samples = 10000
            def is_point_inside_unit_circle(p):
                x, y = random.random(), random.random()
                return 1 if x*x + y*y < 1 else 0

            count = s_session.sparkContext.parallelize(range(num_samples)) \
                             .map(is_point_inside_unit_circle).reduce(lambda a, b: a + b)
            
            pi = 4.0 * count / num_samples
            st.success(f"Il calcolo distribuito su Spark ha restituito Pi ≈ {pi}")
    else:
        st.warning("Spark Master non disponibile.")