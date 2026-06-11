import streamlit as st
import requests
import json
import time
import os
import base64

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
    
    # L'inserimento del CSS è stato spostato nel componente condiviso render_llm_chat_ui

    models_list = []
    source_used = "Codice locale (Fallback)"
    
    if m_ok:
        try:
            db = m_client["datalake"]
            if "llm_models" not in db.list_collection_names() or db["llm_models"].count_documents({}) == 0:
                default_models = [
                    {'id': 'llama3.2:3b', 'name': 'Veloce', 'type': 'llama', 'description': "Risposte dirette e veloci", 'order': 1},
                    {'id': 'qwen3.5:9b', 'name': 'Ragionamento', 'type': 'qwen', 'description': "Fase di pensiero approfondito", 'order': 2}
                ]
                db["llm_models"].insert_many(default_models)
            
            models_list = list(db["llm_models"].find().sort("order", 1))
            source_used = "MongoDB (Metadata Store)"
        except Exception as e:
            pass



    if not models_list:
        models_list = [
            {"id": "qwen3.5:9b", "name": "Qwen 3.5 (Ragionamento)", "type": "qwen"},
            {"id": "gemma4:e4b", "name": "Google Gemma 4 (Bilanciato)", "type": "gemma"}
        ]
        
    model_names = [m["name"] for m in models_list]

    from functions.llm_utils import render_llm_chat_ui
    prompt_utente, submit_clicked, st.session_state["selected_model"] = render_llm_chat_ui(
        key_prefix="copilot",
        placeholder_text="Chiedi all'assistente IA (es. 'Quali IP ho bloccato nel firewall?')...",
        model_names=model_names,
        default_model=st.session_state.get("selected_model", model_names[0] if model_names else ""),
        source_used=source_used
    )

    selected_model_doc = next((m for m in models_list if m["name"] == st.session_state["selected_model"]), None)
    if selected_model_doc:
        model_id = selected_model_doc["id"]
        model_type = selected_model_doc["type"]
    else:
        model_id = "qwen3.5:9b"
        model_type = "qwen"
        
    is_qwen = model_type == "qwen"
    is_deepseek = model_type == "deepseek"
    is_gemma = model_type == "gemma"

    system_instructions = load_prompt_file(model_type)
    if system_instructions:
        st.caption(f"Prompt di sistema caricato da: `prompts/{model_type}.txt`")
    else:
        st.error("Prompt di sistema non caricato")

    thinking_area = st.empty()
    answer_title = st.empty()
    answer_area = st.empty()
    timer_area = st.empty()

    if not st.session_state.get("copilot_generating") and st.session_state.get("last_answer"):
        if st.session_state.get("last_thinking"):
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

    print(f"[AI_COPILOT] generating={st.session_state.get('copilot_generating')} submit={submit_clicked} prompt={repr(prompt_utente[:30]) if prompt_utente else ''}", flush=True)

    if st.session_state.get("copilot_generating") and submit_clicked:
        prompt = prompt_utente
        print(f"[AI_COPILOT] ENTERING LLM block, model_id={model_id}, prompt={repr(prompt[:40])}", flush=True)
        
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
            print(f"[AI_COPILOT] Calling stream_llm_response model={model_id}", flush=True)
            try:
                gpu_layers = 24 if is_qwen else 12
                from functions.llm_utils import stream_llm_response
                clean_answer, thinking_text, elapsed, thinking_duration = stream_llm_response(
                    model_id=model_id,
                    prompt=prompt_completo,
                    system_instructions=system_instructions,
                    llm_options={
                        "temperature": 0.2,
                        "num_ctx": 4096,
                        "num_gpu": gpu_layers
                    },
                    thinking_area=thinking_area,
                    answer_area=answer_area,
                    timer_area=timer_area,
                    format_sql=False
                )
                
                print(f"[AI_COPILOT] LLM done, clean_answer={repr(str(clean_answer)[:40]) if clean_answer else None}", flush=True)
                if clean_answer is not None:
                    answer_title.markdown("### Risposta:")
                    log_action("Admin", "AskAICopilot", f"Interrogato copilot ({model_id}) su: '{prompt[:40]}...'")
                    
            except Exception as e:
                st.error(f"Impossibile connettersi al server LLM. Dettaglio: {e}")
            finally:
                if 'clean_answer' in locals() and clean_answer:
                    st.session_state["last_answer"] = clean_answer
                if 'thinking_text' in locals() and thinking_text:
                    st.session_state["last_thinking"] = thinking_text
                if 'elapsed' in locals() and elapsed:
                    st.session_state["last_total_time"] = elapsed
                if 'thinking_duration' in locals() and thinking_duration:
                    st.session_state["last_thinking_time"] = thinking_duration
                st.session_state["copilot_generating"] = False
                st.rerun()
