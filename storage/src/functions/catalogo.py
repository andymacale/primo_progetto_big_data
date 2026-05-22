import streamlit as st
import os
import pandas as pd
import datetime
import csv
import io
import time

def log_catalogo_action(m_client, user, action, details):
    try:
        m_client["datalake"]["audit_logs"].insert_one({
            "timestamp": datetime.datetime.now(),
            "user": user,
            "action": action,
            "details": details
        })
    except:
        pass

def validate_and_sanitize_csv(uploaded_file):
    if uploaded_file.size > 10 * 1024 * 1024:
        return False, "File troppo grande. Il limite massimo è 10MB."

    if not uploaded_file.name.lower().endswith('.csv'):
        return False, "Estensione del file non valida. È consentito solo il formato .csv."

    try:
        content_bytes = uploaded_file.read()
        uploaded_file.seek(0)
    except Exception as e:
        return False, f"Impossibile leggere il file: {e}"

    magic_signatures = {
        b'\x7fELF': "Eseguibile ELF (Linux)",
        b'MZ': "Eseguibile PE (Windows)",
        b'%PDF': "File PDF",
        b'PK\x03\x04': "Archivio ZIP/Office (DOCX/XLSX)",
        b'\x1f\x8b': "Archivio GZIP",
        b'\x42\x5a\x68': "Archivio BZIP2",
        b'\xd0\xcf\x11\xe0': "File Microsoft Office Legacy",
        b'\x89PNG\r\n\x1a\n': "Immagine PNG",
        b'\xff\xd8\xff': "Immagine JPEG",
        b'GIF89a': "Immagine GIF",
        b'GIF87a': "Immagine GIF"
    }
    
    for signature, file_type in magic_signatures.items():
        if content_bytes.startswith(signature):
            return False, f"Rilevato file binario non autorizzato ({file_type}). Iniezione bloccata!"

    try:
        content_text = content_bytes.decode('utf-8')
    except UnicodeDecodeError:
        try:
            content_text = content_bytes.decode('latin-1')
        except UnicodeDecodeError:
            return False, "Il file contiene caratteri binari non validi (non è testo codificato UTF-8 o Latin-1)."

    dangerous_keywords = [
        "#!/bin/bash", "#!/bin/sh", "#!/usr/bin/env python",
        "<script>", "</script>", "<?php", "eval(", "exec(", 
        "os.system(", "subprocess.run("
    ]
    for kw in dangerous_keywords:
        if kw in content_text:
            return False, f"Rilevato codice/script sospetto all'interno del file CSV: '{kw}'. Iniezione bloccata!"

    try:
        sample = content_text[:4096]
        try:
            dialect = csv.Sniffer().sniff(sample)
            delimiter = dialect.delimiter
        except Exception:
            delimiter = ','
            for d in [';', '\t', '|']:
                if d in sample:
                    delimiter = d
                    break

        f_io = io.StringIO(content_text)
        reader = csv.reader(f_io, delimiter=delimiter)
        rows = list(reader)
        if not rows:
            return False, "Il file CSV è vuoto."
        
        col_count = len(rows[0])
        if col_count == 0:
            return False, "Struttura CSV non valida (nessuna colonna trovata)."
            
        for i, row in enumerate(rows[:50]):  
            if len(row) != col_count:
                return False, f"Inconsistenza nel numero di colonne alla riga {i+1}."
    except Exception as e:
        return False, f"Struttura CSV corrotta o non valida: {e}"

    dangerous_starts = ('=', '+', '-', '@')
    formula_detected = False
    sanitized_rows = []
    
    for row in rows:
        sanitized_row = []
        for cell in row:
            cell_str = str(cell).strip()
            if cell_str.startswith(dangerous_starts):
                formula_detected = True
                cell_str = "'" + cell_str
            sanitized_row.append(cell_str)
        sanitized_rows.append(sanitized_row)

    return True, {
        "rows": sanitized_rows,
        "delimiter": delimiter,
        "formula_detected": formula_detected,
        "columns": rows[0]
    }

def render_catalogo(m_client, m_ok):
    if m_ok:
        search = st.text_input("", placeholder="Cerca dataset nel catalogo...")
        try:
            query = {"$or": [{"name": {"$regex": search, "$options": "i"}}, {"description": {"$regex": search, "$options": "i"}}]} if search else {}
            catalog = list(m_client["datalake"]["metadata_catalog"].find(query))
            for ds in catalog:
                with st.container(border=True):
                    col_title, col_status = st.columns([4, 1])
                    with col_title:
                        st.subheader(f"Dataset: {ds['name']}")
                    with col_status:
                        if ds.get('format') == "MongoDB Collection" or ds.get('location', '').startswith("mongodb://"):
                            exists = m_ok
                        else:
                            exists = os.path.exists(ds['location']) if "/" in ds['location'] else True
                        if exists:
                            st.success("Online")
                        else:
                            st.error("Offline")
                    
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
                    
                    with st.expander("Visualizza schema"):
                        st.dataframe(pd.DataFrame(ds['schema']), width="stretch", hide_index=True)
                        
                    with st.expander("Visualizza anteprima"):
                        df_preview = None
                        error_msg = ""
                        
                        try:
                            if ds['id'] == "ds_live_sniffer":
                                packets = list(m_client["datalake"]["live_traffic"].find({}, {"_id": 0}).sort("timestamp", -1).limit(10))
                                if packets:
                                    df_preview = pd.DataFrame(packets)
                                else:
                                    error_msg = "Nessun pacchetto ancora catturato nel database."
                            elif ds['id'] == "ds_llm_models":
                                models = list(m_client["datalake"]["llm_models"].find({}, {"_id": 0}).sort("order", 1))
                                if models:
                                    df_preview = pd.DataFrame(models)
                                else:
                                    error_msg = "Nessun modello configurato nel database."
                            elif ds['format'] == "PARQUET":
                                import pyarrow.dataset as py_ds
                                if os.path.exists(ds['location']):
                                    dataset = py_ds.dataset(ds['location'], format='parquet')
                                    batch_iter = dataset.to_batches()
                                    first_batch = next(batch_iter, None)
                                    if first_batch:
                                        df_preview = first_batch.to_pandas().head(10)
                                    else:
                                        error_msg = "Il file Parquet è vuoto."
                                else:
                                    error_msg = f"File non trovato nel percorso: {ds['location']}"
                            elif ds['format'] == "CSV":
                                if os.path.exists(ds['location']):
                                    df_preview = pd.read_csv(ds['location'], nrows=10)
                                else:
                                    error_msg = f"File non trovato nel percorso: {ds['location']}"
                            else:
                                error_msg = f"Formato '{ds['format']}' non supportato per l'anteprima."
                        except Exception as ex:
                            error_msg = f"Errore durante l'anteprima: {ex}"
                            
                        if df_preview is not None:
                            st.write("**Anteprima Dati (Prime 10 righe):**")
                            st.dataframe(df_preview, width="stretch")
                            
                            st.write("**Statistiche Profilazione:**")
                            col_info, col_desc = st.columns([1, 1])
                            with col_info:
                                st.markdown(f"**Colonne totali:** `{len(df_preview.columns)}`")
                                st.markdown("**Tipi di Dato Rilevati:**")
                                dtypes_df = pd.DataFrame({
                                    "Colonna": df_preview.columns,
                                    "Tipo di Dato": [str(t) for t in df_preview.dtypes]
                                })
                                st.dataframe(dtypes_df, width="stretch", hide_index=True)
                            with col_desc:
                                numeric_cols = df_preview.select_dtypes(include=['number']).columns
                                if len(numeric_cols) > 0:
                                    st.markdown("**Statistiche Colonne Numeriche (Preview):**")
                                    st.dataframe(df_preview[numeric_cols].describe().T, width="stretch")
                                else:
                                    st.info("Nessuna colonna numerica rilevata nella preview per le statistiche descrittive.")
                        else:
                            st.info(error_msg or "Impossibile generare l'anteprima.")
                            
                    if ds['id'] not in ["ds_historical_nids", "ds_live_sniffer", "ds_llm_models"]:
                        with st.expander("Gestione Metadati (Cancellazione)"):
                            st.warning("**ATTENZIONE**: Questa azione rimuoverà il dataset dal Catalogo dei metadati. Se si tratta di un file caricato, il file fisico verrà rimosso in modo definitivo.")
                            
                            confirm_delete = st.checkbox(f"Confermo di voler eliminare il dataset '{ds['name']}'", key=f"del_conf_{ds['id']}")
                            if st.button("Elimina Dataset", key=f"del_btn_{ds['id']}", disabled=not confirm_delete):
                                try:
                                    m_client["datalake"]["metadata_catalog"].delete_one({"id": ds['id']})
                                    
                                    if ds['format'] == "CSV" and os.path.exists(ds['location']):
                                        os.remove(ds['location'])
                                        
                                    log_catalogo_action(m_client, "Admin", "DeleteDataset", f"Dataset '{ds['name']}' (ID: {ds['id']}) rimosso correttamente.")
                                    st.success(f"Dataset '{ds['name']}' eliminato con successo!")
                                    time.sleep(1)
                                    st.rerun()
                                except Exception as delete_err:
                                    st.error(f"Errore durante l'eliminazione: {delete_err}")
                    
                    last_update = ds['created_at']
                    if ds['id'] == "ds_live_sniffer":
                        last_pkt = m_client["datalake"]["live_traffic"].find_one(sort=[("timestamp", -1)])
                        if last_pkt:
                            last_update = datetime.datetime.fromtimestamp(last_pkt['timestamp'])
                    st.markdown(f"*Ultimo aggiornamento: {last_update.strftime('%H:%M:%S')} ({last_update.strftime('%d-%m-%Y')})*")
        except Exception as e:
            st.error(f"Errore catalogo: {e}")
            
        st.markdown("---")
        with st.expander("Aggiungi nuovo dataset (CSV)"):
            st.write("Carica un file CSV per validarlo ed inserirlo nel Data Lake con meccanismi di Security by Design.")
            
            with st.form(key="upload_csv_form"):
                nome_ds = st.text_input("Nome Dataset", placeholder="Es. Traffico Uffici Milano")
                desc_ds = st.text_input("Descrizione", placeholder="Es. Log di traffico del dipartimento di Milano...")
                cat_ds = st.selectbox("Categoria", ["Traffico Rete", "Audit Logs", "Threat Intelligence", "Anagrafiche", "Altro"])
                uploaded_file = st.file_uploader("Seleziona File CSV", type=["csv"])
                
                submit_upload = st.form_submit_button("Carica")
                
            if submit_upload:
                if not nome_ds.strip() or not desc_ds.strip():
                    st.warning("Nome e Descrizione sono obbligatori.")
                elif uploaded_file is None:
                    st.warning("Seleziona un file CSV da caricare.")
                else:
                    is_valid, result = validate_and_sanitize_csv(uploaded_file)
                    if not is_valid:
                        st.error(f"**Blocco Sicurezza (File Injection Rilevata)**: {result}")
                        log_catalogo_action(m_client, "Admin", "UploadBlocked", f"File: {uploaded_file.name} - Motivo: {result}")
                    else:
                        try:
                            save_dir = "/home/andy/Documenti/primo_progetto_big_data/storage/data/ingested"
                            if not os.path.exists(save_dir):
                                os.makedirs(save_dir, exist_ok=True)
                            
                            save_filename = f"{nome_ds.lower().replace(' ', '_')}_{int(time.time())}.csv"
                            save_path = os.path.join(save_dir, save_filename)
                            
                            with open(save_path, 'w', newline='', encoding='utf-8') as f_out:
                                writer = csv.writer(f_out, delimiter=result['delimiter'])
                                writer.writerows(result['rows'])
                                
                            m_client["datalake"]["metadata_catalog"].insert_one({
                                "id": f"ds_{int(time.time())}",
                                "name": nome_ds,
                                "description": desc_ds,
                                "location": save_path,
                                "format": "CSV",
                                "category": cat_ds,
                                "source": f"Uploaded File ({uploaded_file.name})",
                                "schema": [{"col_name": col, "type": "String"} for col in result['columns']],
                                "created_at": datetime.datetime.now()
                             })
                            
                            log_msg = f"Dataset '{nome_ds}' inserito correttamente. Salvo in {save_filename}."
                            if result['formula_detected']:
                                log_msg += " (Rilevate e bonificate formule CSV)."
                                st.warning("**Formula Injection Rilevata**: Alcune formule pericolose (es. '=', '+') sono state bonificate con successo.")
                            
                            st.success(f"Dataset caricato con successo! {log_msg}")
                            log_catalogo_action(m_client, "Admin", "UploadSuccess", f"Dataset: {nome_ds} - File: {uploaded_file.name} - Formule bonificate: {result['formula_detected']}")
                            
                            st.rerun()
                        except Exception as e:
                            st.error(f"Errore durante l'ingestione del file: {e}")
    else:
        st.error("MongoDB disconnesso. Impossibile caricare il catalogo dei metadati.")
