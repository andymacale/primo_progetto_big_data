import streamlit as st
import socket
import time
import datetime

def render_homepage(m_client, m_ok, get_spark_session, force_spark_reset):
    st.header("🏠 Cockpit Stato Data Center")
    st.write("Monitoraggio generale in tempo reale e salute delle infrastrutture Big Data.")
    
    # --- SEZIONE CONNETTIVITÀ SERVIZI ---
    st.subheader("🔌 Connettività Servizi")
    c_col1, c_col2 = st.columns(2)
    
    with c_col1:
        with st.container(border=True):
            st.markdown("#### Database")
            if m_ok:
                st.success("MongoDB: Collegato 🟢")
            else:
                st.error("MongoDB: Disconnesso 🔴")
                
    with c_col2:
        with st.container(border=True):
            st.markdown("#### Calcolo Distribuito")
            s_ok = False
            try:
                s_test = get_spark_session()
                s_test.conf.get("spark.app.name")
                st.success("Spark Master: Collegato 🟢")
                s_ok = True
            except Exception as e:
                force_spark_reset()
                try:
                    s_test = get_spark_session()
                    s_test.conf.get("spark.app.name")
                    st.success("Spark Master: Collegato (Auto-ripristinato) 🟢")
                    s_ok = True
                except Exception as ex:
                    st.error(f"Spark Master: Disconnesso 🔴\n {ex}")
                    
    st.markdown("---")
    
    # --- METRICHE E RISORSE ---
    st.subheader("📊 Statistiche Ingestione & Risorse")
    kpi1, kpi2, kpi3 = st.columns(3)
    
    # Stato Database
    with kpi1:
        with st.container(border=True):
            st.markdown("### 🗄️ Datalake (MongoDB)")
            if m_ok:
                try:
                    num_ips = m_client["datalake"]["blocked_ips"].count_documents({})
                    num_logs = m_client["datalake"]["audit_logs"].count_documents({})
                    st.metric("IP Bloccati (Firewall)", f"{num_ips}")
                    st.metric("Log di Audit Totali", f"{num_logs:,}")
                except Exception as e:
                    st.caption(f"Errore caricamento statistiche: {e}")
            else:
                st.metric("IP Bloccati", "N/D")
                st.metric("Log di Audit Totali", "N/D")
                
    # Stato Cluster di Calcolo
    with kpi2:
        with st.container(border=True):
            st.markdown("### ⚡ Analytics (Spark)")
            if s_ok:
                st.metric("Master URL", "spark://spark-master:7077")
                st.caption("Pronto ad elaborare job ad alte prestazioni.")
            else:
                st.metric("Master URL", "Sconnesso")
                
    # Stato Sniffer Live
    with kpi3:
        with st.container(border=True):
            st.markdown("### 🛰️ Live Traffic Sniffer")
            if m_ok:
                try:
                    num_packets = m_client["datalake"]["live_traffic"].count_documents({})
                    st.metric("Pacchetti Sniffati (Capped)", f"{num_packets:,} / 5,000")
                except Exception as e:
                    st.caption(f"Dettaglio: {e}")
            else:
                st.metric("Pacchetti", "N/D")

    # Stato Salute Sistema
    st.markdown("---")
    st.subheader("🛡️ Stato di Salute del Network")
    
    if m_ok:
        try:
            ora_limite = time.time() - 60
            recent_alerts_count = m_client["datalake"]["alerts"].count_documents({"timestamp": {"$gt": ora_limite}})
            
            if recent_alerts_count > 0:
                st.error(f"⚠️ Attenzione! Rilevati {recent_alerts_count} allarmi di sicurezza negli ultimi 60 secondi.")
            else:
                st.success("✅ Nessun allarme o tentativo di intrusione attivo negli ultimi 60 secondi. Il Data Center è sicuro.")
        except Exception as e:
            st.caption(f"Impossibile valutare gli allarmi di salute: {e}")
