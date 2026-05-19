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
    st.header("Assistente IA")
    st.write("Interroga le IA ospitate nel nodo `llm` del Data Center.")
    
    # Carica lo stile CSS dal file esterno o relativo
    current_dir = os.path.dirname(__file__)
    src_dir = os.path.dirname(current_dir)
    css_path = os.path.join(src_dir, "templates", "gemini_style.css")
    if not os.path.exists(css_path):
        css_path = "/app/templates/gemini_style.css"
    if not os.path.exists(css_path):
        css_path = "templates/gemini_style.css"
        
    if os.path.exists(css_path):
        with open(css_path, "r", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

    import base64
    import streamlit.components.v1 as components

    def get_base64_image(path):
        if os.path.exists(path):
            try:
                ext = os.path.splitext(path)[1].lower().replace(".", "")
                mime = f"image/{ext}" if ext in ["png", "webp", "jpeg", "jpg"] else "image/png"
                with open(path, "rb") as f:
                    data = f.read()
                return f"data:{mime};base64,{base64.b64encode(data).decode()}"
            except:
                pass
        return None

    # Percorsi per le icone personalizzate cercate dall'utente
    play_path = os.path.join(src_dir, "templates", "img", "play.webp")
    if not os.path.exists(play_path):
        play_path = "/app/templates/img/play.webp"
    if not os.path.exists(play_path):
        play_path = "templates/img/play.webp"

    stop_path = os.path.join(src_dir, "templates", "img", "stop.png")
    if not os.path.exists(stop_path):
        stop_path = "/app/templates/img/stop.png"
    if not os.path.exists(stop_path):
        stop_path = "templates/img/stop.png"

    send_b64 = get_base64_image(play_path)
    stop_b64 = get_base64_image(stop_path)

    # Iniezione dello stile CSS personalizzato per le icone
    css_style = """
    <style>
    /* Centra verticalmente gli elementi all'interno del form/barra di ricerca */
    div[data-testid="stForm"] div[data-testid="stHorizontalBlock"] {
        align-items: center !important;
        gap: 0px !important;
    }
    
    /* Input di testo a larghezza piena e senza margini superflui */
    div[data-testid="stForm"] div[data-testid="stTextInput"] {
        width: 100% !important;
        margin-bottom: 0px !important;
    }

    /* Allinea a destra la colonna/pulsante di sottomissione */
    div[data-testid="stForm"] div[data-testid="stFormSubmitButton"] {
        display: flex !important;
        justify-content: flex-end !important;
        width: 100% !important;
    }

    /* Struttura base dei pulsanti stile icona */
    div[data-testid="stForm"] div[data-testid="stFormSubmitButton"] button {
        background-color: transparent !important;
        border: none !important;
        box-shadow: none !important;
        padding: 0px !important;
        margin: 0px 0px 0px auto !important;
        width: 40px !important;
        height: 40px !important;
        min-width: 40px !important;
        cursor: pointer !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        border-radius: 50% !important;
        transition: transform 0.1s ease-in-out, background-color 0.1s !important;
    }

    div[data-testid="stForm"] div[data-testid="stFormSubmitButton"] button:hover {
        transform: scale(1.1) !important;
        background-color: rgba(255, 255, 255, 0.1) !important;
    }
    """

    if st.session_state.get("generating", False):
        if stop_b64:
            css_style += f"""
            div[data-testid="stForm"] div[data-testid="stFormSubmitButton"] button {{
                background-image: url('{stop_b64}') !important;
                background-size: 60px 60px !important;
                background-repeat: no-repeat !important;
                background-position: center !important;
                color: transparent !important;
            }}
            div[data-testid="stForm"] div[data-testid="stFormSubmitButton"] button * {{
                display: none !important;
            }}
            """
    else:
        if send_b64:
            css_style += f"""
            div[data-testid="stForm"] div[data-testid="stFormSubmitButton"] button {{
                background-image: url('{send_b64}') !important;
                background-size: 24px 24px !important;
                background-repeat: no-repeat !important;
                background-position: center !important;
                color: transparent !important;
            }}
            div[data-testid="stForm"] div[data-testid="stFormSubmitButton"] button * {{
                display: none !important;
            }}
            """

    css_style += "</style>"
    st.markdown(css_style, unsafe_allow_html=True)

    # Inizializzazione session state per la generazione e persistenza dati
    if "generating" not in st.session_state:
        st.session_state["generating"] = False
    if "current_prompt" not in st.session_state:
        st.session_state["current_prompt"] = ""
    if "last_answer" not in st.session_state:
        st.session_state["last_answer"] = ""
    if "last_thinking" not in st.session_state:
        st.session_state["last_thinking"] = ""
    if "selected_model" not in st.session_state:
        st.session_state["selected_model"] = "Qwen 2.5 (Veloce)"
    if "last_total_time" not in st.session_state:
        st.session_state["last_total_time"] = 0.0
    if "last_thinking_time" not in st.session_state:
        st.session_state["last_thinking_time"] = 0.0


    # Creazione della Chat Input Pill con sostituzione dinamica del pulsante Invia/Ferma
    prompt_utente = ""
    submit_clicked = False

    if st.session_state["generating"]:
        with st.form(key="gemini_stop_form", border=False):
            # Riga 1: Input disabilitato e pulsante Ferma allineato in alto
            col_input, col_submit = st.columns([11, 1])
            with col_input:
                st.text_input(
                    "Chiedi a CyberCop...",
                    value=st.session_state["current_prompt"],
                    disabled=True,
                    label_visibility="collapsed"
                )
            with col_submit:
                stop_clicked = st.form_submit_button("Ferma", use_container_width=True)
                
            if stop_clicked:
                st.session_state["generating"] = False
                st.rerun()
                
        # Riga 2: Selezione modello sotto l'input (fuori dal form per reattività)
        col_model, _ = st.columns([4.5, 7.5])
        with col_model:
            st.selectbox(
                "Scegli modello:",
                ["Qwen 2.5 (Veloce)", "DeepSeek R1 (Ragionamento)"],
                index=0 if st.session_state["selected_model"] == "Qwen 2.5 (Veloce)" else 1,
                label_visibility="collapsed",
                disabled=True
            )
    else:
        with st.form(key="gemini_chat_form", border=False):
            # Riga 1: Input abilitato e pulsante Invia allineato in alto
            col_input, col_submit = st.columns([11, 1])
            with col_input:
                prompt_utente = st.text_input(
                    "Chiedi",
                    placeholder="Chiedi all'assistente IA(es. 'Quali IP ho bloccato nel firewall?')...",
                    label_visibility="collapsed"
                )
            with col_submit:
                submit_clicked = st.form_submit_button("Invia", use_container_width=True)
                
        if submit_clicked:
            if prompt_utente.strip():
                st.session_state["generating"] = True
                st.session_state["current_prompt"] = prompt_utente
                st.session_state["last_answer"] = ""
                st.session_state["last_thinking"] = ""
                st.session_state["last_total_time"] = 0.0
                st.session_state["last_thinking_time"] = 0.0
                st.rerun()
                
        # Riga 2: Selezione modello sotto l'input (fuori dal form per reattività)
        col_model, _ = st.columns([4.5, 7.5])
        with col_model:
            modello_scelto = st.selectbox(
                "Scegli modello:",
                ["Qwen 2.5 (Veloce)", "DeepSeek R1 (Ragionamento)"],
                index=0 if st.session_state["selected_model"] == "Qwen 2.5 (Veloce)" else 1,
                label_visibility="collapsed"
            )
            st.session_state["selected_model"] = modello_scelto

    # Determinazione del modello selezionato
    model_id = "qwen2.5:0.5b"
    if "DeepSeek" in st.session_state["selected_model"]:
        model_id = "deepseek-r1:1.5b"
    is_qwen = "qwen" in model_id

    # Blocchi di output persistenti
    thinking_area = st.empty()
    answer_title = st.empty()
    answer_area = st.empty()
    timer_area = st.empty()

    # Mostra la risposta precedente se presente e non stiamo generando
    if not st.session_state["generating"] and st.session_state.get("last_answer"):
        # Mostra il ragionamento solo per DeepSeek se presente
        if not is_qwen and st.session_state.get("last_thinking"):
            cleaned_think = clean_llm_text(st.session_state["last_thinking"])
            last_think = st.session_state.get("last_thinking_time", 0.0)
            expander_title = f"Ragionato in {last_think:.2f}''" if last_think > 0 else "Ragionamento"
            with thinking_area:
                with st.expander(expander_title, expanded=False):
                    st.markdown(f"<div style='background-color:#1e1e24; padding:12px; border-radius:4px; font-style:italic; color:#d6a2e8;'>{cleaned_think}</div>", unsafe_allow_html=True)

        cleaned_ans = clean_llm_text(st.session_state["last_answer"])
        answer_title.markdown("### Risposta:")
        answer_area.markdown(cleaned_ans)

        # Mostra il tempo totale dell'ultima esecuzione sotto la risposta
        last_tot = st.session_state.get("last_total_time", 0.0)
        if last_tot > 0:
            timer_area.markdown(
                f"<div style='font-size:12px; opacity:0.8; margin-top:5px; text-align:right;'>Tempo totale: <strong>{last_tot:.2f}''</strong></div>",
                unsafe_allow_html=True
            )

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

        with st.spinner("Elaborazione in corso..."):
            try:
                start_time = time.time()
                thinking_duration = 0.0
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
                                
                                # Calcolo del tempo di ragionamento dinamico per DeepSeek
                                if not is_qwen and thinking_token:
                                    thinking_duration = time.time() - start_time
                                    
                                # Visualizzazione del Timer e Statistiche in tempo reale (solo Tempo Totale)
                                timer_area.markdown(
                                    f"<div style='font-size:12px; opacity:0.8; margin-top:5px; text-align:right;'>Tempo totale: <strong>{elapsed:.2f}''</strong></div>",
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
                                    exp_title = f"Ragionamento in corso: {thinking_duration:.2f}''" if 'thinking_duration' in locals() and thinking_duration > 0 else "Ragionamento in corso..."
                                    thinking_area.markdown(
                                        f"<div style='background-color:#1e1e24; border-left:4px solid #9b59b6; padding:12px; border-radius:4px; font-style:italic; color:#d6a2e8; margin-bottom:15px;'>"
                                        f"<div style='font-weight:bold; margin-bottom:5px; font-size:12px; opacity:0.8;'>{exp_title}</div>"
                                        f"{cleaned_thinking}"
                                        f"</div>",
                                        unsafe_allow_html=True
                                    )
                                
                                # Visualizzazione della risposta finale
                                if clean_answer:
                                    cleaned_answer = clean_llm_text(clean_answer)
                                    answer_title.markdown("### Risposta:")
                                    answer_area.markdown(cleaned_answer)
                                    
                        # Registra l'azione nel log di sicurezza al termine
                        log_action("Admin", "AskAICopilot", f"Interrogato copilot ({model_id}) su: '{prompt[:40]}...'")
                    else:
                        st.error(f"Errore di comunicazione con il server LLM: Stato {response.status_code}")
            except Exception as e:
                st.error(f"Impossibile connettersi al container LLM a http://2.0.0.226:11434. Dettaglio: {e}")
            finally:
                if 'clean_answer' in locals() and clean_answer:
                    st.session_state["last_answer"] = clean_answer
                if 'thinking_text' in locals() and thinking_text:
                    st.session_state["last_thinking"] = thinking_text
                if 'elapsed' in locals():
                    st.session_state["last_total_time"] = elapsed
                if 'thinking_duration' in locals() and thinking_duration:
                    st.session_state["last_thinking_time"] = thinking_duration
                # Ripristina lo stato al termine della generazione
                st.session_state["generating"] = False
                st.rerun()
