# Relazione Tecnica — Primo Progetto Big Data
## Piattaforma Integrata per il Monitoraggio e l'Analisi della Sicurezza di Rete

---

## 1. Introduzione

Il presente progetto realizza una piattaforma Big Data end-to-end per il monitoraggio, l'analisi e la risposta automatica alle minacce di sicurezza di rete. L'infrastruttura simula un ambiente enterprise realistico attraverso **Kathara**, uno strumento di emulazione di reti basato su container Docker, e integra tecnologie eterogenee: **Apache Spark** per l'elaborazione distribuita, **MongoDB** come Data Lake, modelli **LLM locali** (Large Language Models) tramite Ollama e una **dashboard amministrativa** sviluppata con Streamlit.

Il filo conduttore del progetto è il dato: dal dataset storico di traffico di rete all'ingestion live dei pacchetti, fino all'analisi interattiva via SQL e all'interrogazione in linguaggio naturale con l'intelligenza artificiale. Il tutto orchestrato in un'unica interfaccia amministrativa accessibile via browser.

### Tecnologie Principali

| Componente | Tecnologia |
|---|---|
| Emulazione di rete | Kathara (Docker-based) |
| Elaborazione distribuita | Apache Spark (Master + Worker) |
| Data Lake | MongoDB 7 |
| Dataset NIDS | BigFlow-NIDS (Kaggle) |
| Formato di storage | Apache Parquet |
| Dashboard | Python / Streamlit |
| Visualizzazioni | Altair |
| Intelligenza Artificiale | Ollama (LLM locali: Llama 3.2, Qwen 3.5) |
| Routing di rete | FRRouting (BGP, OSPF, EVPN-VXLAN) |

---

## 2. Architettura dell'Infrastruttura

### 2.1 Topologia di Rete

La rete è stata progettata e configurata interamente dall'autore del progetto. L'ambiente simula un'infrastruttura enterprise articolata in **tre sistemi autonomi (AS)**:

- **AS1** — Rete locale con router BGP (r1–r4), nodo DNS (`local`) e nodo attacker per i test di sicurezza.
- **AS2** — Data Center, cuore del sistema. Implementa un **fabric Clos EVPN-VXLAN** con due Top-of-Fabric (tof_1, tof_2), due Spine (spike_1, spike_2) e due Leaf (leaf_1, leaf_2). Ospita tutti i servizi applicativi.
- **AS3** — Rete esterna (`nsnet`, `nsroot`) che simula la connettività Internet con DNS autoritativo e routing BGP verso gli altri AS.

Il router **r5** svolge il ruolo di **gateway perimetrale del Data Center** e ospita il firewall dinamico, rappresentando il punto di confine tra AS1 e AS2.

### 2.2 Servizi del Data Center

Il Data Center è distribuito sul fabric EVPN-VXLAN e ospita i seguenti container specializzati:

| Nodo | Immagine Custom | Ruolo |
|---|---|---|
| `spark` | `kathara-spark-custom` | Apache Spark Master + Worker |
| `mongo_db` | `kathara-mongo-custom` | MongoDB — Data Lake |
| `llm` | `kathara-llm-custom` | Server LLM (Ollama) con GPU |
| `admin` | `kathara-admin-custom` | Dashboard Streamlit |
| `web_server` | `kathara-webserver-custom` | Web server statico |
| `sniffer` | `kathara/base` | Cattura del traffico (tcpdump) |

---

## 3. Il Dataset: BigFlow-NIDS

### 3.1 Origine e Caratteristiche

Il dataset utilizzato è **BigFlow-NIDS**, disponibile pubblicamente su Kaggle. Si tratta di un dataset per il rilevamento delle intrusioni di rete (Network Intrusion Detection System — NIDS) che raccoglie flussi di traffico etichettati, distinguendo il traffico legittimo da quello malevolo.

Il dataset è stato caricato e preprocessato in formato **Apache Parquet**, che garantisce:
- **Compressione columnar** per ridurre lo spazio su disco
- **Schema-on-read** per la flessibilità nella proiezione delle colonne
- **Compatibilità nativa** con Spark SQL senza necessità di parsing

Il file è collocato nel percorso condiviso `/opt/spark/data/processed/BigFlow-NIDS.parquet`, accessibile sia dal nodo Spark che dal container Admin tramite volume Docker.

### 3.2 Schema Principale

Il dataset contiene flussi di rete con le seguenti colonne chiave, utilizzate nelle query analitiche:

| Campo | Tipo | Descrizione |
|---|---|---|
| `IPV4_SRC_ADDR` | String | Indirizzo IP sorgente del flusso |
| `IPV4_DST_ADDR` | String | Indirizzo IP destinazione del flusso |
| `L4_SRC_PORT` | Integer | Porta sorgente (Layer 4) |
| `L4_DST_PORT` | Integer | Porta destinazione (Layer 4) |
| `PROTOCOL` | Integer | Protocollo (6=TCP, 17=UDP, 1=ICMP) |
| `IN_BYTES` | Long | Byte ricevuti nel flusso |
| `OUT_BYTES` | Long | Byte trasmessi nel flusso |
| `IN_PKTS` | Long | Pacchetti ricevuti |
| `OUT_PKTS` | Long | Pacchetti trasmessi |
| `FLOW_DURATION_MILLISECONDS` | Long | Durata del flusso in millisecondi |
| `FLOW_START_MILLISECONDS` | Long | Timestamp di inizio del flusso |
| `label` / `Attack` | String | Classificazione: Benign / tipo di attacco |

Il dataset contiene oltre **66 milioni di record**, suddivisi tra traffico benigno e diverse categorie di attacco, rendendolo particolarmente adatto per testare le performance di un cluster Spark in scenari di analisi ad alto volume.

---

## 4. Pipeline di Ingestione Dati

### 4.1 Ingestione Dataset Storico

Il dataset BigFlow-NIDS in formato Parquet viene letto direttamente da Spark tramite l'API `spark.read.parquet()` e registrato come **Temporary View SQL** (`traffico_nids`), consentendo l'interrogazione via Spark SQL senza necessità di caricare l'intero dataset in memoria.

```python
df = spark.read.parquet("/opt/spark/data/processed/BigFlow-NIDS.parquet")
df.createOrReplaceTempView("traffico_nids")
```

### 4.2 Ingestione Live (PCAP Ingestor)

Il modulo `pcap_ingestor.py` implementa un ingestore in tempo reale che monitora il file `analisi_traffico.pcap` prodotto dal nodo sniffer. Il processo:

1. Legge il file PCAP tramite la libreria **Scapy** (`rdpcap`)
2. Estrae i campi rilevanti per ogni pacchetto (IP sorgente, destinazione, protocollo)
3. Inserisce i record nella **Capped Collection** `live_traffic` di MongoDB (limite: 5.000 pacchetti, 10 MB)
4. Analizza il traffico in tempo reale per rilevare pattern di attacco e generare alert
5. Si mette in polling con intervallo di 1 secondo

La collezione è di tipo **Capped** (circolare), il che garantisce che i dati più vecchi vengano automaticamente rimpiazzati senza che la dimensione del database cresca indefinitamente.

### 4.3 Catalogo Metadati

Il modulo `init_metadata.py` inizializza un **catalogo dei metadati** nella collezione MongoDB `metadata_catalog`. Il catalogo registra i dataset disponibili con il loro schema, formato, categoria e posizione, replicando il concetto di un **Data Catalog** enterprise (simile ad Apache Atlas o AWS Glue Data Catalog).

I dataset registrati di default sono:

| ID | Nome | Formato | Categoria |
|---|---|---|---|
| `ds_historical_nids` | BigFlow-NIDS Historical Dataset | Parquet | Network Security |
| `ds_live_sniffer` | Live Network Traffic | PCAP / MongoDB | Live Monitoring |
| `ds_llm_models` | Catalogo Modelli LLM | MongoDB Collection | AI / Config |

---

## 5. Elaborazione Distribuita con Apache Spark

### 5.1 Configurazione del Cluster

Il cluster Spark opera in modalità **Standalone** con un Master e un Worker nello stesso container, configurato con le seguenti risorse:

```
SPARK_WORKER_CORES=2
SPARK_WORKER_MEMORY=4G
Master URL: spark://spark-master:7077
```

La connessione al cluster dalla dashboard avviene tramite `SparkSession.builder`, con il connettore MongoDB per Spark (`mongo-spark-connector_2.12-10.3.0.jar`) caricato come JAR esterno, che consente la Data Federation tra sorgenti Parquet e collezioni MongoDB in una singola query SQL.

### 5.2 Data Federation con Spark SQL

Una delle funzionalità avanzate del sistema è il **Data Lake Explorer**, che monta come View federate:

- `storico_parquet` → dal file Parquet su disco
- `live_mongo` → dalla collezione `live_traffic` su MongoDB

Le due sorgenti dati eterogenee diventano interrogabili con una singola istruzione Spark SQL, come:

```sql
SELECT s.IPV4_SRC_ADDR, l.summary
FROM storico_parquet s
JOIN live_mongo l ON s.IPV4_SRC_ADDR = l.src
LIMIT 10
```

### 5.3 Sicurezza sulle Query SQL

La console SQL esposta all'amministratore implementa un meccanismo di **whitelist delle istruzioni**: sono ammesse esclusivamente le istruzioni `SELECT` e i Common Table Expression (`WITH ... AS`). Qualsiasi istruzione DDL o DML (`INSERT`, `UPDATE`, `DELETE`, `DROP`, `CREATE`, etc.) viene intercettata e bloccata prima di essere inviata a Spark, con un messaggio di errore esplicativo.

---

## 6. Analisi del Traffico e Visualizzazioni

Questo capitolo costituisce il nucleo del progetto. Tutte le analisi vengono eseguite su Spark SQL e i risultati visualizzati nella dashboard tramite la libreria **Altair**, basata sulla specifica dichiarativa Vega-Lite. I risultati delle query vengono memorizzati in `st.session_state` per evitare rielaborazioni inutili ad ogni re-render dell'interfaccia.

### 6.1 Rilevamento Anomalie e Classificazione degli Attacchi

**Obiettivo**: identificare e classificare i flussi malevoli presenti nel dataset, escludendo il traffico benigno.

La query `rilevamento_anomalie.sql` implementa una logica di **classificazione rule-based** basata sulle porte di destinazione e sui volumi di traffico:

```sql
WITH traffico AS (
    SELECT
        CASE
            WHEN l4_dst_port = 179 OR l4_src_port = 179 THEN 'BGP Hijacking/Exploit'
            WHEN l4_dst_port = 22                        THEN 'SSH Brute Force'
            WHEN l4_dst_port = 53                        THEN 'DNS Amplification'
            WHEN l4_dst_port IN (80, 443)                THEN 'Web Attack (HTTP/S)'
            WHEN l4_dst_port = 21                        THEN 'FTP File Ingestion Exploit'
            WHEN flow_duration_milliseconds < 100
                 AND in_pkts > 1000                      THEN 'L3/L4 Flood (DDoS)'
            WHEN in_pkts > 5000
                 AND in_bytes > 100000                   THEN 'Volumetric DDoS'
            ELSE 'Altro / Malicious General'
        END AS vettore_attacco,
        label AS etichetta_dataset,
        COUNT(*) AS occorrenze,
        ROUND(AVG(flow_duration_milliseconds), 2) AS durata_media_flusso,
        SUM(in_pkts + out_pkts) AS pacchetti_totali,
        SUM(in_bytes + out_bytes) AS traffico_b
    FROM traffico_nids
    WHERE label != 'Benign'
    GROUP BY 1, 2
)
SELECT *, <formula_conversione_bytes> AS traffico_h
FROM traffico
ORDER BY traffico_b DESC
```

Il campo `traffico_h` converte automaticamente i byte in un formato leggibile (KB, MB, GB, TB) tramite una formula `CASE` su soglie potenze di 1024.

Il **risultato** è una tabella dei flussi anomali raggruppati per vettore d'attacco, con la possibilità di bloccare con un click l'IP attaccante direttamente dalla dashboard. La query identifica anche i **Top 5 attaccanti** (via `top_attaccanti.sql`) con il numero di flussi malevoli e il volume di traffico generato.

### 6.2 Bilanciamento del Dataset

**Obiettivo**: analizzare la distribuzione delle classi di traffico per valutare il bilanciamento del dataset (rilevante in ottica di Machine Learning).

```sql
SELECT Attack AS label, COUNT(*) AS occorrenze
FROM traffico_nids
GROUP BY Attack
```

Il risultato viene visualizzato come **grafico a barre orizzontale** (Altair `mark_bar`) con le classi ordinate per frequenza decrescente. Vengono inoltre calcolate le **percentuali** di ogni classe sul totale, esponendo il rapporto tra traffico benigno e malevolo e l'eventuale sbilanciamento tra le diverse tipologie di attacco.

**Perché è importante**: un dataset fortemente sbilanciato (dove la classe "Benign" rappresenta la grande maggioranza dei record) può portare a modelli di classificazione con alta accuracy ma bassa recall sulle classi di attacco. Questa analisi evidenzia visivamente tale problematica.

### 6.3 Distribuzione dei Protocolli e delle Porte

**Obiettivo**: identificare quali protocolli e porte di destinazione sono maggiormente coinvolti nel traffico, sia benigno che malevolo.

```sql
SELECT 
    L4_DST_PORT AS port,
    CASE 
        WHEN PROTOCOL = 6  THEN 'TCP'
        WHEN PROTOCOL = 17 THEN 'UDP'
        WHEN PROTOCOL = 1  THEN 'ICMP'
        ELSE CAST(PROTOCOL AS STRING)
    END AS protocol_name,
    label,
    COUNT(*) AS flow_count,
    AVG(IN_BYTES + OUT_BYTES) AS avg_bytes
FROM traffico_nids
GROUP BY 1, 2, 3
ORDER BY flow_count DESC
LIMIT 50
```

Il risultato è un **istogramma a barre impilate** (stacked bar chart Altair) in cui:
- L'asse Y riporta le porte di destinazione più trafficate
- L'asse X mostra il numero di flussi
- Il colore distingue la classificazione dell'attacco (label)
- Il tooltip riporta dettagli su protocollo, porta, conteggio flussi e byte medi

Questa visualizzazione permette di identificare immediatamente le porte "calde" (es. 80, 443, 22, 53, 179) e la natura del traffico che le attraversa.

### 6.4 Andamento Temporale del Traffico (Serie Storica)

**Obiettivo**: analizzare l'evoluzione del traffico nel tempo, suddiviso per categoria, per identificare picchi, pattern ricorrenti o finestre temporali di attività malevola.

```sql
SELECT 
    date_trunc('minute', from_unixtime(FLOW_START_MILLISECONDS / 1000)) AS time_window,
    label,
    SUM(IN_BYTES + OUT_BYTES) AS total_bytes,
    COUNT(*) AS flow_count
FROM traffico_nids
GROUP BY 1, 2
ORDER BY 1 ASC
```

La funzione `date_trunc('minute', ...)` aggrega i flussi in finestre temporali di un minuto, mentre `from_unixtime` converte il timestamp in millisecondi nel formato datetime di Spark.

Il grafico prodotto è un **line chart multi-serie** (Altair `mark_line`) con:
- Asse X: finestra temporale (orario)
- Asse Y: volume di traffico in byte
- Colore: classificazione del flusso (una linea per ogni label)

### 6.5 Top Talkers — Matrice Sorgente/Destinazione

**Obiettivo**: individuare le coppie IP (sorgente → destinazione) che generano il maggior volume di traffico, per identificare eventuali comportamenti anomali o concentrazioni di flusso.

```sql
SELECT 
    IPV4_SRC_ADDR AS source_ip,
    IPV4_DST_ADDR AS destination_ip,
    label,
    SUM(IN_BYTES + OUT_BYTES) AS total_bytes,
    COUNT(*) AS flow_count
FROM traffico_nids
WHERE IPV4_SRC_ADDR IS NOT NULL AND IPV4_DST_ADDR IS NOT NULL
GROUP BY 1, 2, 3
ORDER BY total_bytes DESC
LIMIT 100
```

Il risultato è una **heatmap** (Altair `mark_rect`) a matrice IP sorgente × IP destinazione, dove l'intensità del colore (scala `reds`) indica il volume di byte totali scambiati. Il tooltip riporta src, dst, byte totali, numero di flussi e classificazione.

Questa visualizzazione è particolarmente efficace per evidenziare attacchi volumetrici o scansioni di rete sistematiche, dove uno stesso IP sorgente appare in molte celle della matrice.

---

## 7. Sistema di Sicurezza e Risposta Automatica

### 7.1 Architettura del Sistema di Alerting

Il sistema di sicurezza implementa un **ciclo chiuso di rilevamento e risposta** che collega il traffico di rete al firewall perimetrale in modo completamente automatico:

```
Sniffer (tcpdump) → PCAP → pcap_ingestor.py → MongoDB (alerts)
       ↓
Dashboard Admin → blocca IP → UDP → firewall_daemon.py (r5) → iptables
       ↓
       MongoDB (blocked_ips) ← sync_firewall.py (all'avvio)
```

### 7.2 Rilevamento Real-Time nel PCAP Ingestor

Il modulo `pcap_ingestor.py`, durante l'ingestione dei pacchetti live, analizza ogni flusso TCP alla ricerca di pattern sospetti:

| Condizione Rilevata | Alert Generato |
|---|---|
| Porta 179 (BGP) | `POSSIBILE BGP HIJACKING` |
| Porta 21 (FTP) | `TENTATIVO FILE INJECTION` |
| Porta 22 (SSH) | `TENTATIVO BRUTE FORCE SSH` |
| Porta 80 (HTTP) da IP esterni | `POSSIBILE DOS/SYN FLOOD` |
| Porta 27017 (MongoDB) da IP esterni | `ACCESSO DATABASE NON AUTORIZZATO` |

Gli alert vengono scritti nella collezione `alerts` di MongoDB con severità (`INFO` se già bloccato, `CRITICAL` se attivo) e stato (`MITIGATED` o `ACTIVE`). Se l'IP sorgente è già presente nella **black-list**, il blocco avviene automaticamente senza intervento dell'amministratore.

### 7.3 Firewall Perimetrale Dinamico

Il nodo r5, gateway del Data Center, esegue in background il demone `firewall_daemon.py`. Questo processo ascolta su una socket **UDP** (porta 5000) i comandi di blocco nel formato `BLOCK:<ip>`.

Alla ricezione di un comando, applica due regole `iptables` sul router:

```bash
iptables -A FORWARD -s <ip> -j REJECT --reject-with icmp-port-unreachable
iptables -A INPUT   -s <ip> -j REJECT --reject-with icmp-port-unreachable
```

Il blocco avviene a livello **L3 della rete**, quindi agisce sul forwarding del router indipendentemente dai servizi applicativi.

### 7.4 Persistenza e Sincronizzazione

Per garantire che le regole firewall sopravvivano al riavvio del container Admin, lo script `sync_firewall.py` viene eseguito all'avvio del nodo: legge tutti gli IP bloccati da MongoDB e ri-invia i comandi UDP a r5, ripristinando le regole iptables. Questo meccanismo implementa un principio di **state recovery** che rende il sistema resiliente ai riavvii.

### 7.5 Privacy Mode

La dashboard include una modalità **Privacy Mode** (toggle nella sidebar) che maschera l'ultimo ottetto degli indirizzi IP nella vista Live Sniffer (es. `192.168.1.xxx`), consentendo la visualizzazione del traffico senza esporre gli indirizzi completi in ambienti condivisi.

---

## 8. Catalogo Dati e Security by Design

### 8.1 Gestione del Catalogo

La sezione **Catalogo** della dashboard implementa un sistema di gestione dei dataset che replica le funzionalità di un Data Catalog enterprise:

- **Ricerca full-text** sui campi `name` e `description` tramite espressioni regolari MongoDB
- **Stato online/offline** verificato in tempo reale (esistenza file su disco o connettività MongoDB)
- **Anteprima dei dati** (prime 10 righe) con statistiche descrittive automatiche per le colonne numeriche
- **Schema del dataset** visualizzato in forma tabellare
- **Eliminazione controllata** con doppia conferma (checkbox + pulsante) e rimozione fisica del file

### 8.2 Validazione File con Security by Design

Il caricamento di nuovi dataset CSV implementa una pipeline di validazione multilivello progettata con il principio di **Security by Design**:

1. **Limite dimensione**: rifiuto dei file superiori a 10 MB
2. **Estensione**: ammessi solo file `.csv`
3. **Magic bytes**: analisi dei primi byte per rilevare file binari mascherati da CSV (ELF, PE, PDF, ZIP, PNG, JPEG, etc.)
4. **Encoding**: verifica della codifica UTF-8 o Latin-1
5. **Keyword injection**: rilevamento di script shell, PHP, JavaScript o comandi `eval`/`exec` nel contenuto
6. **Struttura CSV**: verifica della consistenza del numero di colonne su tutte le righe
7. **Formula injection**: sanitizzazione delle celle che iniziano con `=`, `+`, `-`, `@` (vettori di attacco per spreadsheet injection)

Ogni tentativo di caricamento malevolo viene registrato nell'**Audit Log** con il motivo del blocco.

---

## 9. Assistente IA (AI Copilot)

### 9.1 Architettura LLM

Il nodo `llm` ospita un'istanza **Ollama** con accesso GPU (passthrough `NVIDIA_VISIBLE_DEVICES=all`), esposta sulla porta 11434. I modelli configurati di default sono:

| Modello | ID Ollama | Caratteristica |
|---|---|---|
| Veloce | `llama3.2:3b` | Risposte dirette e rapide, senza fase di reasoning |
| Ragionamento | `qwen3.5:9b` | Reasoning esplicito con tag `<think>`, risposte più approfondite |

La configurazione dei modelli è gestita dinamicamente da MongoDB (collezione `llm_models`), consentendo di aggiungere o rimuovere modelli senza modificare il codice.

### 9.2 Streaming e Reasoning

Il modulo `llm_utils.py` gestisce la comunicazione con Ollama tramite l'endpoint `/api/generate` in modalità **streaming** (chunked HTTP). Per ogni token ricevuto:

- I token di **ragionamento** (tag `<think>`) vengono estratti e visualizzati in un box separato con sfondo scuro e bordo viola
- I token della **risposta finale** vengono visualizzati in tempo reale nel pannello principale
- Un timer mostra il tempo di generazione in tempo reale

### 9.3 RAG Contestuale (Retrieval-Augmented Generation)

Per le domande riguardanti la sicurezza della rete, l'AI Copilot implementa una forma semplificata di **RAG (Retrieval-Augmented Generation)**: prima di inviare il prompt al modello, il sistema recupera da MongoDB i dati contestuali più rilevanti (IP bloccati, alert recenti) e li inietta nel prompt come contesto. In questo modo il modello risponde basandosi sui dati reali del Data Center, anziché su conoscenza generica.

### 9.4 Generazione SQL via LLM

Il **Data Lake Explorer** integra un assistente IA specializzato nella generazione di query Spark SQL. Il prompt di sistema (`sql_llama.txt`, `sql_qwen.txt`) istruisce il modello a generare esclusivamente codice SQL valido, senza markdown. La risposta viene renderizzata come blocco di codice SQL con syntax highlighting.

---

## 10. Dashboard Amministrativa

La dashboard è sviluppata in **Python/Streamlit** e suddivisa in 5 tab principali:

| Tab | Modulo | Contenuto |
|---|---|---|
| Homepage | `homepage.py` | Stato servizi (MongoDB, Spark, LLM, Sicurezza), KPI globali |
| Catalogo | `catalogo.py` | Data Catalog con preview, schema, upload CSV sicuro, Data Lake Explorer |
| Analisi | `spark_analysis.py` | 6 tab analitiche: anomalie, bilanciamento, sicurezza, timeline, protocolli, top talkers |
| Sniffer | `live_sniffer.py` | Traffico live da MongoDB, download PCAP per Wireshark |
| Assistente IA | `ai_copilot.py` | Chat con LLM locale con RAG contestuale |

### Funzionalità Trasversali

- **Alert banner**: un banner di stato in cima alla pagina mostra in tempo reale se sono presenti attacchi attivi negli ultimi 5 minuti
- **Auto-refresh**: la sidebar offre un toggle per il refresh automatico ogni 2 secondi (per il monitoraggio live)
- **Hard Reset Spark**: pulsante per liberare la cache della sessione Spark e riconnettersi al cluster in caso di disconnessione
- **Audit Trail**: ogni azione rilevante (blocco IP, upload dataset, interrogazione LLM) viene registrata in MongoDB con timestamp, utente e dettaglio

---

## 11. Conclusioni

Il progetto ha realizzato una piattaforma Big Data completa che dimostra l'applicazione pratica delle seguenti competenze:

- **Ingestion di dati eterogenei**: combinazione di un dataset storico in formato Parquet da Kaggle con dati live da cattura PCAP, entrambi accessibili tramite lo stesso layer di query Spark SQL.
- **Elaborazione distribuita**: Apache Spark ha elaborato oltre 66 milioni di record del dataset BigFlow-NIDS, con query SQL complesse su aggregazioni, window functions temporali e join tra sorgenti dati diverse.
- **Visualizzazione analitica**: sei visualizzazioni interattive realizzate con Altair (barre, line chart, heatmap) offrono prospettive complementari sul traffico di rete, dalla distribuzione delle classi alla matrice dei flussi tra coppie di IP.
- **Architettura Data Lake**: MongoDB funziona come Data Lake operazionale per i dati live, mentre Parquet copre l'analisi storica. Il Data Catalog centralizza i metadati di entrambe le sorgenti.
- **Sicurezza applicata**: il sistema implementa un ciclo chiuso di risposta agli incidenti, dalla rilevazione al blocco firewall, con persistenza su database e meccanismi di audit trail.
- **Integrazione AI**: l'utilizzo di LLM locali con RAG contestuale e generazione di query SQL rappresenta un'evoluzione verso sistemi di analisi in linguaggio naturale (NL2SQL), senza dipendere da servizi cloud esterni.

### Possibili Sviluppi Futuri

- Integrazione di un modello di Machine Learning (es. Random Forest o XGBoost) addestrato direttamente su Spark MLlib per la classificazione automatica del traffico
- Implementazione di un sistema di alerting proattivo basato su soglie dinamiche calcolate su finestre temporali scorrevoli
- Estensione del Data Lake Explorer con supporto alla scrittura in modalità append per la creazione di report permanenti
- Configurazione multi-worker Spark su nodi distinti per testare lo scaling orizzontale del cluster

---

*Relazione redatta il 03/06/2026*
