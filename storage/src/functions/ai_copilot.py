import streamlit as st
import requests
import json
import time
import re
import os
import datetime

def clean_llm_text(text: str) -> str:
    replacements = {
        "incalabrinamento": "anomalia di instradamento",
        "incalabrinamenti": "anomalie di instradamento",
        "spettoso": "sospetto",
        "spettosa": "sospetta",
        "spettosi": "sospetti",
        "spettose": "sospette",
        "behinderini": "ostacoli",
        "behinderin": "ostacolo",
        "behinderina": "ostacolo",
        "protatteno": "protetto",
        "protatteni": "protetti",
        "impieghiati": "impiegati",
        "seguentiatione": "segmentazione",
        "buonuo": "buongiorno",
        "buonuso": "buongiorno",
        "bonacci": "buongiorno",
        "Ferretti le Firewalls": "Rafforza i firewall",
        "ferretti le firewalls": "rafforza i firewall",
        "funne": "funziona",
        "丰富的zza": "ricchezza",
        "iutrecenti": "i recenti",
        "lutrecenti": "i recenti",
        "incassatura": "iniezione",
        "incassature": "iniezioni",
        "alerti": "allarmi",
        "sameframe": "sistema",
        "nel data del": "in data",
        "nel data": "in data",
        "related": "correlati",
        "sulles": "sui",
        "quest'è": "questa è",
        "auto scanning": "scansione automatica",
        "auto-scanning": "scansione automatica",
        "state": "stato",
        "evidendeci": "evidenziando",
        "evidendesi": "evidenziandosi",
        "evidende": "evidenzia"
    }
    cleaned = text
    for word, rep in replacements.items():
        pattern = re.compile(re.escape(word), re.IGNORECASE)
        cleaned = pattern.sub(rep, cleaned)
    return cleaned

def render_ai_copilot(m_client, m_ok, log_action):
    st.header("🤖 Assistente Decisionale IA (Ollama)")
    st.write("Interroga le intelligenze artificiali locali ospitate nel nodo `llm` del Data Center per chiarimenti tecnici, mitigazione delle minacce e hardening di rete.")
    
    # Carica lo stile CSS dal file esterno o relativo
    current_dir = os.path.dirname(__file__)
    css_path = os.path.join(current_dir, "templates", "gemini_style.css")
    if not os.path.exists(css_path):
        css_path = "/app/templates/gemini_style.css"
    if not os.path.exists(css_path):
        css_path = "templates/gemini_style.css"
        
    if os.path.exists(css_path):
        with open(css_path, "r", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

    # Inizializzazione session state per la generazione
    if "generating" not in st.session_state:
        st.session_state["generating"] = False
    if "current_prompt" not in st.session_state:
        st.session_state["current_prompt"] = ""

    # Creazione della Chat Input Pill con sostituzione dinamica del pulsante Invia/Ferma
    prompt_utente = ""
    submit_clicked = False

    if st.session_state["generating"]:
        col_input, col_submit = st.columns([10, 2])
        with col_input:
            st.text_input(
                "Chiedi a CyberCop...",
                value=st.session_state["current_prompt"],
                disabled=True,
                label_visibility="collapsed"
            )
        with col_submit:
            if st.button("Ferma ⏹️", key="stop_llm_btn", use_container_width=True):
                st.session_state["generating"] = False
                st.rerun()
    else:
        with st.form(key="gemini_chat_form", border=False):
            col_input, col_submit = st.columns([10, 2])
            with col_input:
                prompt_utente = st.text_input(
                    "Chiedi a CyberCop...",
                    placeholder="Chiedi a CyberCop ed invia con Invio (es. 'Quali IP ho bloccato nel firewall?')...",
                    label_visibility="collapsed"
                )
            with col_submit:
                submit_clicked = st.form_submit_button("Invia ➔", use_container_width=True)
                
        if submit_clicked and prompt_utente.strip():
            st.session_state["generating"] = True
            st.session_state["current_prompt"] = prompt_utente
            st.rerun()

    # Controlli sotto il chat pill (fuori dal form per re-run reattivo immediato!)
    col_model, col_chk = st.columns([4, 8])
    with col_model:
        modello_scelto = st.selectbox(
            "Scegli modello:",
            ["Qwen 2.5 (0.5B)", "DeepSeek R1 (1.5B)"],
            index=1,
            label_visibility="collapsed",
            disabled=st.session_state["generating"]
        )

    # Determinazione del modello selezionato
    model_id = "qwen2.5:0.5b"
    if "DeepSeek" in modello_scelto:
        model_id = "deepseek-r1:1.5b"
    is_qwen = "qwen" in model_id

    # Checkbox reattiva: si disabilita all'istante se viene selezionato Qwen o se si sta generando!
    with col_chk:
        mostra_thinking = st.checkbox(
            "💡 Mostra Ragionamento (DeepSeek)", 
            value=False, 
            help="Se attivo, mostra la fase di ragionamento in tempo reale.",
            disabled=is_qwen or st.session_state["generating"]
        )

    # Blocchi di output persistenti
    thinking_title = st.empty()
    thinking_area = st.empty()
    answer_title = st.empty()
    answer_area = st.empty()
    timer_area = st.empty()

    # Esecuzione della generazione (se attiva)
    if st.session_state["generating"]:
        prompt = st.session_state["current_prompt"]
        
        # --- RICONOSCIMENTO DELLE CONVERSAZIONI GENERICHE / SALUTI ---
        p_lower = prompt.strip().lower()
        security_keywords = [
            "ip", "block", "bloccat", "firewall", "attacc", "alert", "allarm", 
            "traffico", "sniffer", "sicurezza", "nids", "intrusion", "catalogo", 
            "dataset", "mongo", "database", "cyber", "porta", "port", "conness"
        ]
        is_security_query = any(kw in p_lower for kw in security_keywords)
        greetings = ["ciao", "buongiorno", "salve", "buonasera", "test", "hola", "hello", "hi", "hey", "chi sei", "aiuto"]
        is_greeting = any(g in p_lower for g in greetings)
        is_generic = (len(p_lower) <= 15 or is_greeting) and not is_security_query

        if is_generic:
            prompt_completo = f"Rispondi in lingua italiana: {prompt}"
            system_instructions = "Rispondi sempre in lingua italiana in modo cortese, naturale e conciso. Rispondi cordialmente ai saluti."
        else:
            # --- RAG: Ingestione dinamica dello stato di MongoDB ---
            contesto_sicurezza = ""
            if m_ok:
                try:
                    # Estrae i top 5 IP bloccati al momento
                    blocked_ips = list(m_client["datalake"]["blocked_ips"].find({"status": "BLOCKED"}).limit(5))
                    # Estrae gli ultimi 5 allarmi registrati
                    alerts = list(m_client["datalake"]["alerts"].find().sort("timestamp", -1).limit(5))
                    
                    contesto_sicurezza += "\n[CONTESTO REALE DEL DATA CENTER - DA MONGO DB]\n"
                    contesto_sicurezza += "IP bloccati nel firewall edge:\n"
                    if blocked_ips:
                        for ip_doc in blocked_ips:
                            b_at = ip_doc.get('blocked_at')
                            b_at_str = b_at.strftime('%Y-%m-%d %H:%M') if hasattr(b_at, 'strftime') else str(b_at)
                            contesto_sicurezza += f"- IP: {ip_doc.get('ip')} | Bloccato il: {b_at_str} | Motivo: {ip_doc.get('reason')}\n"
                    else:
                        contesto_sicurezza += "- Nessun IP bloccato al momento.\n"
                        
                    contesto_sicurezza += "\nAllarmi di sicurezza recenti:\n"
                    if alerts:
                        for a in alerts:
                            contesto_sicurezza += f"- Alert: {a.get('message')} | Stato: {a.get('status')} | Severità: {a.get('severity')}\n"
                    else:
                        contesto_sicurezza += "- Nessun allarme recente.\n"
                except Exception as ex:
                    contesto_sicurezza += f"\n(Errore nel recupero dei dati da MongoDB: {ex})\n"
            
            prompt_completo = f"""[IMPORTANTE - RISPONDI IN LINGUA ITALIANA]
Usa questi dati reali del Data Center per rispondere alla domanda dell'utente se pertinenti:
{contesto_sicurezza}

Domanda dell'utente: {prompt}"""

            system_instructions = (
                "Sei un esperto di sicurezza informatica per il Data Center. "
                "Rispondi sempre in italiano corretto, chiaro e professionale. "
                "Usa termini appropriati (segmentazione, impiegati, interrogazione, orario)."
            )

        with st.spinner("L'IA sta elaborando la risposta in tempo reale..."):
            try:
                start_time = time.time()
                # Chiamata in streaming al container llm locale su VNI 300
                with requests.post(
                    "http://2.0.0.226:11434/api/generate",
                    json={
                        "model": model_id,
                        "prompt": prompt_completo,
                        "system": system_instructions,
                        "options": {
                            "temperature": 0.3,
                            "top_p": 0.85,
                            "num_predict": 800
                        },
                        "stream": True
                    },
                    stream=True,
                    timeout=(5, 300)
                ) as response:
                    
                    if response.status_code == 200:
                        thinking_text = ""
                        clean_answer = ""
                        
                        for line in response.iter_lines():
                            if line:
                                chunk = json.loads(line.decode('utf-8'))
                                response_token = chunk.get("response", "")
                                thinking_token = chunk.get("thinking", "")
                                elapsed = time.time() - start_time
                                
                                # Visualizzazione del Timer e Statistiche in tempo reale
                                timer_area.markdown(
                                    f"<div style='font-size:12px; opacity:0.8; margin-top:5px; text-align:right;'>⏳ Tempo elaborazione attivo: <strong>{elapsed:.2f} secondi</strong></div>",
                                    unsafe_allow_html=True
                                )
                                
                                if is_qwen:
                                    clean_answer += response_token
                                else:
                                    if thinking_token:
                                        thinking_text += thinking_token
                                    if response_token:
                                        clean_answer += response_token
                                
                                # Visualizzazione del ragionamento (solo DeepSeek)
                                if not is_qwen and thinking_text:
                                    cleaned_thinking = clean_llm_text(thinking_text)
                                    if mostra_thinking:
                                        thinking_title.markdown("💭 **Fase di Ragionamento (AI Thinking):**")
                                        thinking_area.markdown(f"<div style='background-color:#1e1e24; border-left:4px solid #9b59b6; padding:12px; border-radius:4px; font-style:italic; color:#d6a2e8;'>{cleaned_thinking}</div>", unsafe_allow_html=True)
                                    else:
                                        thinking_title.caption("💡 *Fase di Ragionamento (Thinking) nascosta dalle impostazioni*")
                                
                                # Visualizzazione della risposta finale
                                if clean_answer:
                                    cleaned_answer = clean_llm_text(clean_answer)
                                    answer_title.markdown("### 🤖 Risposta dell'Assistente IA:")
                                    answer_area.info(cleaned_answer)
                                    
                        # Registra l'azione nel log di sicurezza al termine
                        log_action("Admin", "AskAICopilot", f"Interrogato copilot ({model_id}) su: '{prompt[:40]}...'")
                    else:
                        st.error(f"Errore di comunicazione con il server LLM: Stato {response.status_code}")
            except Exception as e:
                st.error(f"Impossibile connettersi al container LLM a http://2.0.0.226:11434. Dettaglio: {e}")
            finally:
                # Ripristina lo stato al termine della generazione
                st.session_state["generating"] = False
                st.rerun()
