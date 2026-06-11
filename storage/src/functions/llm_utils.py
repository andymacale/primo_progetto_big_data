import streamlit as st
import requests
import json
import time
import re

def stream_llm_response(model_id, prompt, system_instructions, thinking_area, answer_area, timer_area=None, format_sql=False, llm_options=None):
    """
    Gestisce la chiamata in streaming verso il server LLM (Ollama), 
    aggiornando i container Streamlit in tempo reale con il ragionamento (<think>) e la risposta finale.
    Ritorna una tupla: (clean_answer, thinking_text, total_time, thinking_time)
    """
    start_time = time.time()
    thinking_duration = 0.0
    thinking_text = ""
    clean_answer = ""
    raw_stream = ""
    
    if "3b" in model_id.lower():
        system_instructions += "\nNon inserire pensieri o ragionamenti extra, dai direttamente la risposta finale."
        
    options_payload = {
        "temperature": 0.3,
        "top_p": 0.85,
        "num_predict": 2048
    }
    if llm_options:
        options_payload.update(llm_options)
    
    try:
        with requests.post(
            "http://llm.cyber.net:11434/api/generate",
            json={
                "model": model_id,
                "prompt": prompt,
                "system": system_instructions,
                "options": options_payload,
                "stream": True
            },
            stream=True,
            timeout=(5, 300)
        ) as response:
            
            if response.status_code == 200:
                for line in response.iter_lines():
                    if line:
                        chunk = json.loads(line.decode('utf-8'))
                        response_token = chunk.get("response", "")
                        thinking_token = chunk.get("thinking", "")
                        elapsed = time.time() - start_time
                        
                        if thinking_token:
                            thinking_duration = elapsed
                            thinking_text += thinking_token
                            clean_answer += response_token
                        else:
                            raw_stream += response_token
                            if "<think>" in raw_stream:
                                thinking_duration = elapsed
                                t_match = re.search(r'<think>(.*?)(?:</think>|$)', raw_stream, re.DOTALL)
                                if t_match:
                                    thinking_text = t_match.group(1)
                                c_answer = re.sub(r'<think>.*?(?:</think>|$)', '', raw_stream, flags=re.DOTALL)
                                clean_answer = c_answer
                            else:
                                clean_answer = raw_stream
                                
                        if timer_area:
                            timer_area.markdown(
                                f"<div style='font-size:12px; opacity:0.8; margin-top:5px; text-align:right;'>Tempo totale: <strong>{elapsed:.2f}''</strong></div>",
                                unsafe_allow_html=True
                            )
                        
                        if thinking_text:
                            exp_title = f"Ragionamento in corso: {thinking_duration:.2f}''" if thinking_duration > 0 else "Ragionamento in corso..."
                            thinking_area.markdown(
                                f"<div style='background-color:#1e1e24; border-left:4px solid #9b59b6; padding:12px; border-radius:4px; font-style:italic; color:#d6a2e8; margin-bottom:15px;'> "
                                f"<div style='font-weight:bold; margin-bottom:5px; font-size:12px; opacity:0.8;'>{exp_title}</div>"
                                f"{thinking_text.strip()}"
                                f"</div>",
                                unsafe_allow_html=True
                            )
                        
                        if clean_answer.strip():
                            if format_sql:
                                answer_area.code(clean_answer.strip(), language="sql")
                            else:
                                answer_area.markdown(clean_answer.strip())
                
                return clean_answer, thinking_text, time.time() - start_time, thinking_duration
            else:
                st.error(f"Errore di comunicazione con il server LLM: Stato {response.status_code}")
                return None, None, 0.0, 0.0
                
    except Exception as e:
        st.error(f"Errore durante la generazione LLM: {e}")
        return None, None, 0.0, 0.0

def render_llm_chat_ui(key_prefix, placeholder_text, model_names, default_model, source_used=None):
    """
    Renderizza l'interfaccia utente standard per l'interazione con l'LLM, 
    incluso il CSS per il pulsante Play/Stop e la gestione dello stato di generazione.
    Ritorna una tupla: (prompt_utente, submit_clicked, modello_selezionato)
    """
    import os
    import base64
    
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

    gen_key = f"{key_prefix}_generating"
    prompt_key = f"{key_prefix}_current_prompt"
    model_key = f"{key_prefix}_selected_model"
    
    if gen_key not in st.session_state:
        st.session_state[gen_key] = False
    if prompt_key not in st.session_state:
        st.session_state[prompt_key] = ""
    if model_key not in st.session_state or st.session_state[model_key] not in model_names:
        st.session_state[model_key] = default_model if default_model in model_names else (model_names[0] if model_names else "")
        
    # Fix for StreamlitAPIException when options change: clear the selectbox widget state if invalid
    active_key = f"{key_prefix}_sel_active"
    disabled_key = f"{key_prefix}_sel_disabled"
    if active_key in st.session_state and st.session_state[active_key] not in model_names:
        del st.session_state[active_key]
    if disabled_key in st.session_state and st.session_state[disabled_key] not in model_names:
        del st.session_state[disabled_key]

    bg_img = ""
    bg_size = "24px 24px"
    if st.session_state.get(gen_key, False):
        if stop_b64:
            bg_img = f"url('{stop_b64}')"
            bg_size = "60px 60px"
    else:
        if send_b64:
            bg_img = f"url('{send_b64}')"
            bg_size = "24px 24px"
            
    # Usa una classe univoca per il form se possibile, ma st.markdown applica globalmente
    # Visto che il bottone è renderizzato in tempo reale, lo stile globale è tollerabile.
    st.markdown(f"""
        <style>
        :root {{
            --btn-bg-img: {bg_img};
            --btn-bg-size: {bg_size};
        }}
        </style>
    """, unsafe_allow_html=True)

    prompt_utente = ""
    submit_clicked = False
    
    if st.session_state[gen_key]:
        with st.form(key=f"{key_prefix}_stop_form", border=False):
            col_input, col_submit = st.columns([11, 1])
            with col_input:
                st.text_input("Chiedi", value=st.session_state[prompt_key], disabled=True, label_visibility="collapsed")
            with col_submit:
                stop_clicked = st.form_submit_button("Ferma", width="stretch")
                
            if stop_clicked:
                st.session_state[gen_key] = False
                st.rerun()
                
        col_model, _ = st.columns([4.5, 7.5])
        with col_model:
            modello_selezionato = st.selectbox(
                "Scegli modello:",
                model_names,
                index=model_names.index(st.session_state[model_key]) if st.session_state[model_key] in model_names else 0,
                key=f"{key_prefix}_sel_disabled",
                label_visibility="collapsed",
                disabled=True
            )
    else:
        with st.form(key=f"{key_prefix}_chat_form", border=False):
            col_input, col_submit = st.columns([11, 1])
            with col_input:
                prompt_utente = st.text_input("Chiedi", placeholder=placeholder_text, label_visibility="collapsed")
            with col_submit:
                submit_clicked = st.form_submit_button("Invia", width="stretch")
                
        if submit_clicked and prompt_utente.strip():
            st.session_state[gen_key] = True
            st.session_state[prompt_key] = prompt_utente
            
        col_model, _ = st.columns([4.5, 7.5])
        with col_model:
            modello_selezionato = st.selectbox(
                "Scegli modello:",
                model_names,
                index=model_names.index(st.session_state[model_key]) if st.session_state[model_key] in model_names else 0,
                key=f"{key_prefix}_sel_active",
                label_visibility="collapsed"
            )
            st.session_state[model_key] = modello_selezionato
            if source_used:
                st.caption(f"Configurazione modelli caricata dinamicamente da: `{source_used}`")
                
    if submit_clicked and prompt_utente.strip():
        # Triggeriamo il rerun per aggiornare l'interfaccia (bottone che diventa Stop)
        st.rerun()
        
    return st.session_state[prompt_key] if st.session_state[gen_key] else prompt_utente, st.session_state[gen_key] and prompt_utente == "", modello_selezionato
