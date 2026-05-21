import streamlit as st
import requests
import json
import time
import re
import os
import datetime
import base64
import streamlit.components.v1 as components

def load_prompt_file(model_type):
    current_dir = os.path.dirname(__file__)
    src_dir = os.path.dirname(current_dir)
    prompt_dir = os.path.join(src_dir, "prompts")
    file_path = os.path.join(prompt_dir, f"{model_type}.txt")
    
    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content:
                    return content
        except:
            return None

def render_ai_copilot(m_client, m_ok, log_action, get_spark_session=None):
    st.header("Assistente IA")
    st.write("Interroga le IA ospitate nel nodo `llm` del Data Center.")
    
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

    bg_img = ""
    bg_size = "24px 24px"
    if st.session_state.get("generating", False):
        if stop_b64:
            bg_img = f"url('{stop_b64}')"
            bg_size = "60px 60px"
    else:
        if send_b64:
            bg_img = f"url('{send_b64}')"
            bg_size = "24px 24px"
            
    st.markdown(f"""
        <style>
        :root {{
            --btn-bg-img: {bg_img};
            --btn-bg-size: {bg_size};
        }}
        </style>
    """, unsafe_allow_html=True)

    models_list = []
    source_used = "Codice locale (Fallback)"
    
    if m_ok:
        try:
            db = m_client["datalake"]
            if "llm_models" not in db.list_collection_names() or db["llm_models"].count_documents({}) == 0:
                default_models = [
                    {"id": "qwen2.5:0.5b", "name": "Qwen 2.5 (Veloce)", "type": "qwen", "description": "Risposte istantanee", "order": 1},
                    {"id": "deepseek-r1:1.5b", "name": "DeepSeek R1 (Ragionamento)", "type": "deepseek", "description": "Fase di pensiero approfondito", "order": 2},
                    {"id": "gemma4:e4b", "name": "Google Gemma 4 (Bilanciato)", "type": "gemma", "description": "Risposte dirette e precise", "order": 3}
                ]
                db["llm_models"].insert_many(default_models)
            
            models_list = list(db["llm_models"].find().sort("order", 1))
            source_used = "MongoDB (Metadata Store)"
        except Exception as e:
            pass

    if get_spark_session:
        try:
            s_session = get_spark_session()
            spark_df = s_session.read.format("mongodb")\
                .option("database", "datalake")\
                .option("collection", "llm_models")\
                .load()
            models_list_spark = [row.asDict() for row in spark_df.orderBy("order").collect()]
            if models_list_spark:
                models_list = models_list_spark
                source_used = "Apache Spark (Distributed Collection)"
        except Exception as e:
            pass

    if not models_list:
        models_list = [
            {"id": "qwen2.5:0.5b", "name": "Qwen 2.5 (Veloce)", "type": "qwen"},
            {"id": "deepseek-r1:1.5b", "name": "DeepSeek R1 (Ragionamento)", "type": "deepseek"},
            {"id": "gemma4:e4b", "name": "Google Gemma 4 (Bilanciato)", "type": "gemma"}
        ]
        
    model_names = [m["name"] for m in models_list]

    if "generating" not in st.session_state:
        st.session_state["generating"] = False
    if "current_prompt" not in st.session_state:
        st.session_state["current_prompt"] = ""
    if "last_answer" not in st.session_state:
        st.session_state["last_answer"] = ""
    if "last_thinking" not in st.session_state:
        st.session_state["last_thinking"] = ""
    if "selected_model" not in st.session_state or st.session_state["selected_model"] not in model_names:
        st.session_state["selected_model"] = model_names[0] if model_names else "Qwen 2.5 (Veloce)"
    if "last_total_time" not in st.session_state:
        st.session_state["last_total_time"] = 0.0
    if "last_thinking_time" not in st.session_state:
        st.session_state["last_thinking_time"] = 0.0

    prompt_utente = ""
    submit_clicked = False

    if st.session_state["generating"]:
        with st.form(key="gemini_stop_form", border=False):
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
                
        col_model, _ = st.columns([4.5, 7.5])
        with col_model:
            st.selectbox(
                "Scegli modello:",
                model_names,
                index=model_names.index(st.session_state["selected_model"]) if st.session_state["selected_model"] in model_names else 0,
                label_visibility="collapsed",
                disabled=True
            )
    else:
        with st.form(key="gemini_chat_form", border=False):
            col_input, col_submit = st.columns([11, 1])
            with col_input:
                prompt_utente = st.text_input(
                    "Chiedi",
                    placeholder="Chiedi all'assistente IA (es. 'Quali IP ho bloccato nel firewall?')...",
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
                
        col_model, _ = st.columns([4.5, 7.5])
        with col_model:
            modello_scelto = st.selectbox(
                "Scegli modello:",
                model_names,
                index=model_names.index(st.session_state["selected_model"]) if st.session_state["selected_model"] in model_names else 0,
                label_visibility="collapsed"
            )
            st.session_state["selected_model"] = modello_scelto
            st.caption(f"Configurazione modelli caricata dinamicamente da: `{source_used}`")

    selected_model_doc = next((m for m in models_list if m["name"] == st.session_state["selected_model"]), None)
    if selected_model_doc:
        model_id = selected_model_doc["id"]
        model_type = selected_model_doc["type"]
    else:
        model_id = "qwen2.5:0.5b"
        model_type = "qwen"
        
    is_qwen = model_type == "qwen"
    is_deepseek = model_type == "deepseek"
    is_gemma = model_type == "gemma"

    system_instructions = load_prompt_file(model_type)
    if system_instructions
        st.caption(f"Prompt di sistema caricato da: `prompts/{model_type}.txt`")
    else:
        st.error("Prompt di sistema non caricato")

    thinking_area = st.empty()
    answer_title = st.empty()
    answer_area = st.empty()
    timer_area = st.empty()

    if not st.session_state["generating"] and st.session_state.get("last_answer"):
        if is_deepseek and st.session_state.get("last_thinking"):
            last_think = st.session_state.get("last_thinking_time", 0.0)
            expander_title = f"Ragionato in {last_think:.2f}''" if last_think > 0 else "Ragionamento"
            with thinking_area:
                with st.expander(expander_title, expanded=False):
                    st.markdown(f"<div style='background-color:#1e1e24; padding:12px; border-radius:4px; font-style:italic; color:#d6a2e8;'>{st.session_state['last_thinking']}</div>", unsafe_allow_html=True)

        answer_title.markdown("### Risposta:")
        answer_area.markdown(st.session_state["last_answer"])

        last_tot = st.session_state.get("last_total_time", 0.0)
        if last_tot > 0:
            timer_area.markdown(
                f"<div style='font-size:12px; opacity:0.8; margin-top:5px; text-align:right;'>Tempo totale: <strong>{last_tot:.2f}''</strong></div>",
                unsafe_allow_html=True
            )

    if st.session_state["generating"]:
        prompt = st.session_state["current_prompt"]
        
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
        else:
            contesto_sicurezza = ""
            if m_ok:
                try:
                    blocked_ips = list(m_client["datalake"]["blocked_ips"].find({"status": "BLOCKED"}).limit(5))
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

        with st.spinner("Elaborazione in corso..."):
            try:
                start_time = time.time()
                thinking_duration = 0.0
                with requests.post(
                    "http://2.0.0.226:11434/api/generate",
                    json={
                        "model": model_id,
                        "prompt": prompt_completo,
                        "system": system_instructions,
                        "options": {
                            "temperature": 0.3,
                            "top_p": 0.85,
                            "num_predict": 2048
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
                                
                                if is_deepseek and thinking_token:
                                    thinking_duration = time.time() - start_time
                                    
                                timer_area.markdown(
                                    f"<div style='font-size:12px; opacity:0.8; margin-top:5px; text-align:right;'>Tempo totale: <strong>{elapsed:.2f}''</strong></div>",
                                    unsafe_allow_html=True
                                )
                                
                                if is_qwen or is_gemma:
                                    clean_answer += response_token
                                else:
                                    if thinking_token:
                                        thinking_text += thinking_token
                                    if response_token:
                                        clean_answer += response_token
                                
                                if is_deepseek and thinking_text:
                                    exp_title = f"Ragionamento in corso: {thinking_duration:.2f}''" if 'thinking_duration' in locals() and thinking_duration > 0 else "Ragionamento in corso..."
                                    thinking_area.markdown(
                                        f"<div style='background-color:#1e1e24; border-left:4px solid #9b59b6; padding:12px; border-radius:4px; font-style:italic; color:#d6a2e8; margin-bottom:15px;'> "
                                        f"<div style='font-weight:bold; margin-bottom:5px; font-size:12px; opacity:0.8;'>{exp_title}</div>"
                                        f"{thinking_text}"
                                        f"</div>",
                                        unsafe_allow_html=True
                                    )
                                
                                if clean_answer:
                                    answer_title.markdown("### Risposta:")
                                    answer_area.markdown(clean_answer)
                                    
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
                st.session_state["generating"] = False
                st.rerun()
