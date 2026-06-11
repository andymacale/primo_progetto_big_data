import streamlit as st
import socket
import time
from PIL import Image

def render_homepage(m_client, m_ok, get_spark_session, force_spark_reset, check_spark_alive=None):
    st.subheader("Stato dei servizi e sicurezza")
    c_col1, c_col2, c_col3, c_col4 = st.columns([1, 1, 1, 1])
    
    with c_col1:
        with st.container(border=True):
            try:
                mongo = Image.open("/app/templates/img/mongodb.png")
                st.image(mongo, width="stretch")
            except Exception as e:
                st.error(f"Errore caricamento MongoDB: {e}")
            if m_ok:
                st.success("Online")
            else:
                st.error("Offline")
                
    with c_col2:
        with st.container(border=True):
            try:
                spark = Image.open("/app/templates/img/spark.webp")
                st.image(spark, width="stretch")
            except Exception as e:
                st.error(f"Errore caricamento Spark: {e}")

            s_ok = False
            alive = check_spark_alive if check_spark_alive else (lambda s, **_: s.sql("SELECT 1").collect() or True)
            try:
                s_test = get_spark_session()
                if alive(s_test):
                    st.success("Online")
                    s_ok = True
                else:
                    raise RuntimeError("no response")
            except Exception:
                force_spark_reset()
                try:
                    s_test = get_spark_session()
                    if alive(s_test):
                        st.success("Online")
                        s_ok = True
                    else:
                        raise RuntimeError("no response")
                except Exception:
                    st.error("Offline")
                    
    with c_col3:
        with st.container(border=True):
            try:
                ai_img = Image.open("/app/templates/img/ia.png")
                st.image(ai_img, width="stretch")
            except Exception as e:
                st.caption("AI Copilot")
            
            try:
                s_ollama = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s_ollama.settimeout(2.0)
                s_ollama.connect(("llm.cyber.net", 11434))
                s_ollama.close()
                st.success("Online")
            except Exception as e:
                st.error("Offline")

    with c_col4:
        if m_ok:
            with st.container(border=True):
                try:
                    ora_limite = time.time() - 300
                    recent_alerts_count = m_client["datalake"]["alerts"].count_documents({"timestamp": {"$gt": ora_limite}})
                    
                    if recent_alerts_count > 0:
                        allarme = Image.open("/app/templates/img/allarme.png")
                        st.image(allarme, width="stretch")
                        st.error(f"Rilevati {recent_alerts_count} allarmi (ultimi 5')")
                    else:
                        protetto = Image.open("/app/templates/img/protetto.png")
                        st.image(protetto, width="stretch")
                        st.success("Protetto (ultimi 5')")
                except Exception as e:
                    errore = Image.open("/app/templates/img/errore.png")
                    st.image(errore, width="stretch")
                    st.caption(f"Errore: {e}")
                    
    st.markdown("---")

    st.subheader("Statistiche di ingestione e risorse")
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    
    with kpi1:
        with st.container(border=True):
            st.markdown("### Datalake (MongoDB)")
            if m_ok:
                try:
                    num_logs = m_client["datalake"]["audit_logs"].count_documents({})
                    st.metric("Log di Audit Totali", f"{num_logs:,}")
                except Exception as e:
                    st.caption(f"Errore: {e}")
            else:
                st.metric("Log di Audit Totali", "N/D")
                
    with kpi2:
        with st.container(border=True):
            st.markdown("### Sicurezza (Firewall)")
            if m_ok:
                try:
                    num_ips = m_client["datalake"]["blocked_ips"].count_documents({})
                    st.metric("IP Bloccati (Firewall)", f"{num_ips}")
                except Exception as e:
                    st.caption(f"Errore: {e}")
            else:
                st.metric("IP Bloccati (Firewall)", "N/D")
                
    with kpi3:
        with st.container(border=True):
            st.markdown("### Analytics (Spark)")
            if s_ok:
                st.metric("Stato Cluster", "Attivo")
            else:
                st.metric("Stato Cluster", "Sconnesso")
                
    with kpi4:
        with st.container(border=True):
            st.markdown("### Traffico (Sniffer)")
            if m_ok:
                try:
                    num_packets = m_client["datalake"]["live_traffic"].count_documents({})
                    st.metric("Pacchetti Sniffati", f"{num_packets:,} / 5,000")
                except Exception as e:
                    st.caption(f"Dettaglio: {e}")
            else:
                st.metric("Pacchetti Sniffati", "N/D")
