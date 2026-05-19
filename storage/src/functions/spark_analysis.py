import streamlit as st
import time
import os
import pandas as pd

def render_spark_analysis(m_client, get_spark_session, force_spark_reset, block_ip, log_action):
    st.header("📊 Intelligence Rilevamento Anomalie")
    try:
        s_session = get_spark_session()
        s_session.conf.get("spark.app.name")
        s_ok = True
    except:
        force_spark_reset()
        try:
            s_session = get_spark_session()
            s_session.conf.get("spark.app.name")
            s_ok = True
        except:
            s_ok = False
    
    if s_ok:
        if st.button("Avvia Analisi Real-time") or st.session_state.get("spark_analysis_run", False):
            st.session_state["spark_analysis_run"] = True
            
            # Calcola i risultati Spark se non presenti in session_state
            if "spark_risultati" not in st.session_state or "spark_top_attaccanti" not in st.session_state:
                try:
                    parquet_path = "/opt/spark/data/processed/BigFlow-NIDS.parquet"
                    query_path = "/app/analytics/queries/rilevamento_anomalie.sql"
                    if not os.path.exists(query_path):
                        query_path = "analytics/queries/rilevamento_anomalie.sql"
                    
                    with st.spinner("Elaborazione Spark in corso..."):
                        t_start = time.time()
                        df = s_session.read.parquet(parquet_path)
                        df.createOrReplaceTempView("traffico_nids")
                        
                        # Query 1: Rilevamento Anomalie Generale
                        with open(query_path, 'r') as f:
                            query_sql = f.read()
                        risultati = s_session.sql(query_sql).toPandas()
                        
                        # Query 2: Top Attaccanti Malevoli (caricata da file)
                        query_top_path = "/app/analytics/queries/top_attaccanti.sql"
                        if not os.path.exists(query_top_path):
                            query_top_path = "analytics/queries/top_attaccanti.sql"
                            
                        with open(query_top_path, 'r') as f:
                            query_top_sql = f.read()
                        top_attaccanti = s_session.sql(query_top_sql).toPandas()
                        
                        t_end = time.time()
                        exec_time = round(t_end - t_start, 2)
                        
                        log_action("Admin", "RunSparkAnalysis", f"Eseguito rilevamento anomalie su 66M record in {exec_time}s")
                        
                        st.session_state["spark_risultati"] = risultati
                        st.session_state["spark_top_attaccanti"] = top_attaccanti
                        st.session_state["spark_execution_time"] = exec_time
                except Exception as e:
                    st.error(f"Errore Spark: {e}")
                    st.session_state["spark_analysis_run"] = False
            
            # Rendering dei risultati
            risultati = st.session_state.get("spark_risultati")
            top_attaccanti = st.session_state.get("spark_top_attaccanti")
            
            if risultati is not None and not risultati.empty:
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
                
                st.markdown("---")
                st.subheader("🔍 Correlazione Threat Intelligence (Spark + MongoDB)")
                st.write("I 5 IP attaccanti più attivi nel Data Lake, incrociati con lo stato reale del Firewall.")
                
                if top_attaccanti is not None and not top_attaccanti.empty:
                    # Recupera blocklist aggiornata per il confronto (ad ogni rendering)
                    blocked_list = list(m_client["datalake"]["blocked_ips"].find())
                    blocked_ips = set(b['ip'] for b in blocked_list)
                    
                    # Intestazioni tabella
                    c_h1, c_h2, c_h3, c_h4, c_h5 = st.columns([2, 1, 2, 2, 2])
                    c_h1.markdown("**IP Sospetto**")
                    c_h2.markdown("**Attacchi**")
                    c_h3.markdown("**Classe**")
                    c_h4.markdown("**Stato Firewall**")
                    c_h5.markdown("**Azione**")
                    
                    for idx, row in top_attaccanti.iterrows():
                        ip = row['ip_attaccante']
                        occorrenze = row['occorrenze']
                        classe = row['classe']
                        is_blocked = ip in blocked_ips
                        
                        c_ip, c_occ, c_classe, c_status, c_act = st.columns([2, 1, 2, 2, 2])
                        
                        with c_ip:
                            st.markdown(f"`{ip}`")
                        with c_occ:
                            st.markdown(f"{occorrenze:,}")
                        with c_classe:
                            st.markdown(f"`{classe}`")
                        with c_status:
                            if is_blocked:
                                st.success("🛡️ Protetto")
                            else:
                                st.error("🚨 Attivo (Minaccia)")
                        with c_act:
                            if not is_blocked:
                                if st.button(f"🛡️ Blocca", key=f"spark_block_{ip}_{idx}"):
                                    block_ip(ip)
                                    st.success(f"IP {ip} bloccato!")
                                    st.rerun()
                            else:
                                st.caption("Mitigato")
                else:
                    st.info("Nessun IP attaccante rilevato nel dataset.")
            else:
                st.success("Nessuna anomalia rilevata.")
    else:
        st.warning("Spark Master non disponibile o disconnesso.")
