import streamlit as st
import os
import time
import pandas as pd

def render_live_sniffer(m_client, masking):
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
