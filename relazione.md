# Relazione Tecnica — Primo Progetto Big Data
## Piattaforma Integrata per il Monitoraggio e l'Analisi della Sicurezza di Rete

---

## 1. Introduzione

Il presente progetto realizza una **piattaforma Big Data end-to-end** per l'analisi del traffico di rete. L'infrastruttura simula un ambiente enterprise attraverso **Kathara**, uno strumento di emulazione di reti basato su container Docker, e integra tecnologie eterogenee di elaborazione e visualizzazione dati: **Apache Spark** per il processing distribuito, **MongoDB** come Data Lake operazionale, modelli **LLM locali** (Large Language Models) tramite Ollama e una **dashboard amministrativa** sviluppata con Streamlit.

Il filo conduttore del progetto è il dato: dal dataset storico di traffico di rete (oltre 66 milioni di record) all'ingestion live dei pacchetti, fino all'analisi interattiva via Spark SQL e all'interrogazione in linguaggio naturale con l'intelligenza artificiale. Il tutto orchestrato in un'unica interfaccia amministrativa accessibile via browser.

### Tecnologie Principali

| Componente | Tecnologia |
|---|---|
| Emulazione di rete | Kathara (Docker-based) |
| Elaborazione distribuita | Apache Spark (Standalone Mode) |
| Data Lake | MongoDB 7 |
| Dataset NIDS | BigFlow-NIDS (Kaggle, ~66M record) |
| Formato di storage | Apache Parquet (columnar) |
| Dashboard | Python / Streamlit |
| Visualizzazioni | Altair (Vega-Lite) |
| Intelligenza Artificiale | Ollama (LLM locali: Llama 3.2, Qwen 3.5) |
| Routing di rete | FRRouting (BGP, OSPF, EVPN-VXLAN) |

---

## 2. Architettura dell'Infrastruttura

### 2.1 Topologia di Rete (sintesi)

L'ambiente simula un'infrastruttura enterprise in **tre sistemi autonomi (AS)**. Il cuore del sistema è **AS2 — Data Center**, che implementa un fabric **Clos EVPN-VXLAN** (Top-of-Fabric, Spine, Leaf) e ospita tutti i servizi applicativi. AS1 è la rete locale con i client e il nodo attacker per i test; AS3 simula la connettività Internet esterna con DNS autoritativo. Il router **r5** funge da gateway perimetrale del Data Center.

### 2.2 Servizi del Data Center

| Nodo | Immagine Custom | Ruolo |
|---|---|---|
| `spark` | `kathara-spark-custom` | Apache Spark Master + Worker |
| `mongo_db` | `kathara-mongo-custom` | MongoDB — Data Lake |
| `llm` | `kathara-llm-custom` | Server LLM (Ollama) con GPU passthrough |
| `admin` | `kathara-admin-custom` | Dashboard Streamlit |
| `web_server` | `kathara-webserver-custom` | Web server statico |
| `sniffer` | `kathara/base` | Cattura del traffico (tcpdump) |

---

## 3. Il Dataset: BigFlow-NIDS

### 3.1 Origine e Caratteristiche

Il dataset utilizzato è **BigFlow-NIDS**, disponibile pubblicamente su Kaggle. Si tratta di un dataset per il rilevamento delle intrusioni di rete (NIDS — Network Intrusion Detection System) che raccoglie flussi di traffico etichettati, distinguendo il traffico legittimo (`Benign`) da diverse categorie di attacco (DDoS, Brute Force, ecc.).

Il dataset è stato ingerito e preprocessato in formato **Apache Parquet**, che garantisce:

- **Compressione columnar** per ridurre lo spazio su disco rispetto al CSV originale
- **Schema-on-read** per la proiezione flessibile delle sole colonne necessarie
- **Compatibilità nativa** con Spark SQL senza parsing aggiuntivo

La pipeline di conversione avviene tramite Spark stesso (`spark_ingest.py`): il CSV viene letto con `inferSchema` (sampling 10%), la colonna `label` viene castata a stringa e il risultato viene scritto in Parquet in modalità `overwrite`:

```python
df = spark.read.option("header", "true") \
           .option("inferSchema", "true") \
           .option("samplingRatio", "0.1") \
           .csv("/opt/spark/data/raw/BigFlow-NIDS.csv")
df = df.withColumn("label", df["label"].cast("string"))
df.write.mode("overwrite").parquet("/opt/spark/data/processed/BigFlow-NIDS.parquet")
```

Il file Parquet risiede nel percorso `/opt/spark/data/processed/BigFlow-NIDS.parquet`, montato come volume Docker condiviso tra il nodo `spark` e il container `admin`.

### 3.2 Schema Principale

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
| `FLOW_START_MILLISECONDS` | Long | Timestamp di inizio flusso (epoch ms) |
| `label` / `Attack` | String | Classificazione: Benign / tipo di attacco |

Il dataset contiene oltre **66.355.798 record**, suddivisi tra traffico benigno e diverse categorie di attacco, rendendolo adatto per testare le performance del cluster Spark in scenari di analisi ad alto volume.

---

## 4. MongoDB come Data Lake

### 4.1 Ruolo e Motivazione della Scelta

MongoDB è il componente centrale dell'architettura dati operazionale del progetto. Viene utilizzato come **Data Lake per i dati live e semi-strutturati**, complementare al Parquet storico. La scelta di MongoDB è motivata da:

- **Schema flessibile (schema-less)**: i documenti live (pacchetti PCAP, alert) hanno struttura variabile e non richiedono una schema rigida come un RDBMS
- **Capped Collections**: meccanismo nativo per buffer circolari di dimensione fissa, ideale per stream di dati ad alto throughput
- **Integrazione con Spark**: il connettore `mongo-spark-connector_2.12-10.3.0.jar` permette la Data Federation, rendendo le collezioni MongoDB interrogabili con la stessa sintassi SQL delle sorgenti Parquet
- **Ricerca full-text**: supporto nativo a espressioni regolari nei filtri, utile per il Data Catalog

### 4.2 Database e Collezioni

Il progetto utilizza un unico database `datalake` con le seguenti collezioni:

| Collezione | Tipo | Contenuto |
|---|---|---|
| `live_traffic` | **Capped** (5.000 doc, 10 MB) | Pacchetti live dal sniffer PCAP |
| `alerts` | Standard | Alert di sicurezza generati dall'ingestor |
| `blocked_ips` | Standard | IP bloccati dal firewall con timestamp e motivo |
| `black_list` | Standard | IP in blocco automatico senza intervento umano |
| `white_list` | Standard | IP sempre considerati sicuri (esclusi dagli alert) |
| `metadata_catalog` | Standard | Data Catalog dei dataset disponibili |
| `llm_models` | Standard | Configurazione dei modelli LLM per l'assistente |
| `audit_logs` | Standard | Registro di ogni azione rilevante nella dashboard |

### 4.3 La Capped Collection `live_traffic`

La collezione `live_traffic` è di tipo **Capped**: una struttura dati circolare in cui i documenti più vecchi vengono automaticamente sovrascritti quando si raggiunge il limite configurato. Il vantaggio principale è che la dimensione del database rimane costante indipendentemente dal volume di traffico catturato, senza necessità di operazioni esplicite di pulizia.

```python
db.create_collection("live_traffic", capped=True, size=10 * 1024 * 1024, max=5000)
```

Ogni documento inserito ha la seguente struttura:

```json
{
  "timestamp": 1718000000.123,
  "summary": "Ether / IP / TCP 10.0.1.2:54321 > 10.0.0.3:80 S",
  "length": 66,
  "src": "10.0.1.2",
  "dst": "10.0.0.3",
  "proto": "TCP"
}
```

### 4.4 Il Data Catalog (`metadata_catalog`)

La collezione `metadata_catalog` replicà il concetto di un **Data Catalog enterprise** (simile ad Apache Atlas o AWS Glue Data Catalog). Viene inizializzata da `init_metadata.py` che inserisce tre record, uno per ogni sorgente dati del sistema:

| ID | Nome | Formato | Categoria |
|---|---|---|---|
| `ds_historical_nids` | BigFlow-NIDS Historical Dataset | Parquet | Network Security |
| `ds_live_sniffer` | Live Network Traffic | PCAP / MongoDB | Live Monitoring |
| `ds_llm_models` | Catalogo Modelli LLM | MongoDB Collection | AI / Config |

Ogni record contiene: `id`, `name`, `description`, `source`, `format`, `location`, `category`, `created_at` e un array `schema` che descrive i campi del dataset.

### 4.5 Query MongoDB nella Dashboard

Oltre alle query Spark SQL, la dashboard esegue direttamente query MongoDB per operazioni real-time:

```python
# Recupero IP bloccati (per il RAG dell'assistente IA)
blocked_ips = list(m_client["datalake"]["blocked_ips"]
    .find({"status": "BLOCKED"}).limit(5))

# Alert recenti (ultimi 5, ordinati per timestamp decrescente)
alerts = list(m_client["datalake"]["alerts"]
    .sort("timestamp", -1).limit(5))

# Ricerca full-text nel catalogo tramite regex MongoDB
collection.find({
    "$or": [
        {"name": {"$regex": query, "$options": "i"}},
        {"description": {"$regex": query, "$options": "i"}}
    ]
})
```

---

## 5. Pipeline di Ingestione Dati

### 5.1 Ingestione Dataset Storico (Batch)

Il dataset BigFlow-NIDS in formato Parquet viene letto direttamente da Spark tramite l'API `spark.read.parquet()` e registrato come **Temporary View SQL** (`traffico_nids`), consentendo l'interrogazione via Spark SQL senza caricare l'intero dataset in memoria:

```python
df = spark.read.parquet("/opt/spark/data/processed/BigFlow-NIDS.parquet")
df.createOrReplaceTempView("traffico_nids")
```

### 5.2 Ingestione Live (PCAP Ingestor)

Il modulo `pcap_ingestor.py` implementa un ingestore in tempo reale che monitora il file `analisi_traffico.pcap` prodotto dal nodo sniffer. Il processo opera in polling continuo (intervallo 1 secondo) e mantiene un contatore dei pacchetti già processati per inserire in MongoDB solo i nuovi pacchetti:

1. Legge il file PCAP tramite **Scapy** (`rdpcap`)
2. Estrae i campi rilevanti per ogni pacchetto (IP sorgente/destinazione, protocollo, summary Scapy)
3. Inserisce i nuovi record nella Capped Collection `live_traffic`
4. Analizza il traffico TCP per pattern sospetti e genera alert nella collezione `alerts`
5. Se l'IP sorgente è nella `black_list`, blocca automaticamente via UDP senza intervento dell'amministratore

Il modulo gestisce anche la **rotazione del file PCAP**: se il contatore di pacchetti scende rispetto all'ultima lettura, il file è stato sovrascritto e il contatore viene azzerato.

---

## 6. Elaborazione Distribuita con Apache Spark

### 6.1 Configurazione del Cluster

Il cluster Spark opera in modalità **Standalone** con Master e Worker nello stesso container:

```
SPARK_WORKER_CORES=2
SPARK_WORKER_MEMORY=4G
Master URL: spark://spark-master:7077
```

La `SparkSession` viene creata dalla dashboard con il connettore MongoDB caricato come JAR esterno:

```python
spark = SparkSession.builder \
    .appName("DataLake_Ingestion") \
    .master("spark://spark-master:7077") \
    .config("spark.speculation", "false") \
    .getOrCreate()
```

I risultati delle query vengono memorizzati in `st.session_state` per evitare rielaborazioni ad ogni re-render dell'interfaccia Streamlit.

### 6.2 Data Federation con Spark SQL (Data Lake Explorer)

Una funzionalità avanzata del sistema è il **Data Lake Explorer**, che monta come View federate due sorgenti eterogenee:

- `storico_parquet` → dal file Parquet su disco (`/opt/spark/data/processed/BigFlow-NIDS.parquet`)
- `live_mongo` → dalla collezione `live_traffic` su MongoDB (tramite `mongo-spark-connector`)

Le due sorgenti dati diventano interrogabili con una singola istruzione Spark SQL. Esempio di query federata cross-source:

```sql
SELECT s.IPV4_SRC_ADDR, l.summary
FROM storico_parquet s
JOIN live_mongo l ON s.IPV4_SRC_ADDR = l.src
LIMIT 10
```

### 6.3 Sicurezza sulle Query SQL

La console SQL implementa una **whitelist delle istruzioni**: solo `SELECT` e CTE (`WITH ... AS`) sono ammesse. Qualsiasi DDL o DML (`INSERT`, `UPDATE`, `DELETE`, `DROP`, `CREATE`) viene intercettato prima dell'invio a Spark.

---

## 7. Analisi del Traffico: le Query Spark SQL

Questo capitolo costituisce il nucleo del progetto. Tutte le analisi vengono eseguite via Spark SQL su 66 milioni di record e i risultati visualizzati con **Altair** (Vega-Lite). I file SQL sono separati dal codice Python in `storage/src/analytics/queries/`.

### 7.1 Rilevamento Anomalie e Classificazione degli Attacchi (`rilevamento_anomalie.sql`)

**Obiettivo**: classificare i flussi malevoli per vettore d'attacco usando una logica rule-based sulle porte di destinazione e sui volumi di traffico.

```sql
WITH traffico AS (
    SELECT
        CASE
            WHEN l4_dst_port = 179 OR l4_src_port = 179 THEN 'BGP Hijacking/Exploit'
            WHEN l4_dst_port = 22                        THEN 'SSH Brute Force'
            WHEN l4_dst_port = 53                        THEN 'DNS Amplification'
            WHEN l4_dst_port = 80 OR l4_dst_port = 443  THEN 'Web Attack (HTTP/S)'
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
        ROUND(SUM(in_pkts + out_pkts), 0) AS pacchetti_totali,
        SUM(in_bytes + out_bytes) AS traffico_b
    FROM traffico_nids
    WHERE label != 'Benign'
    GROUP BY 1, 2
)
SELECT vettore_attacco,
       etichetta_dataset,
       occorrenze,
       durata_media_flusso,
       pacchetti_totali,
       traffico_b,
       CASE
           WHEN traffico_b >= 1024.0*1024.0*1024.0*1024.0 THEN CONCAT(ROUND(traffico_b / (1024.0*1024.0*1024.0*1024.0), 2), 'TB')
           WHEN traffico_b >= 1024.0*1024.0*1024.0        THEN CONCAT(ROUND(traffico_b / (1024.0*1024.0*1024.0), 2), 'GB')
           WHEN traffico_b >= 1024.0*1024.0               THEN CONCAT(ROUND(traffico_b / (1024.0*1024.0), 2), 'MB')
           WHEN traffico_b >= 1024.0                      THEN CONCAT(ROUND(traffico_b / 1024.0, 2), 'KB')
           ELSE CONCAT(traffico_b, 'B')
       END AS traffico_h
FROM traffico
ORDER BY traffico_b DESC
```

La colonna `traffico_h` converte i byte in un formato leggibile usando soglie potenze di 1024 (`KB`, `MB`, `GB`, `TB`). Il risultato è una tabella dei flussi anomali ordinati per volume di traffico decrescente.

### 7.2 Top 5 Attaccanti (`top_attaccanti.sql`)

**Obiettivo**: identificare gli IP sorgente responsabili del maggior numero di flussi malevoli.

```sql
SELECT ipv4_src_addr AS ip_attaccante,
       COUNT(*) AS occorrenze,
       SUM(in_bytes + out_bytes) AS traffico_b,
       label AS classe
FROM traffico_nids
WHERE label != 'Benign'
GROUP BY ipv4_src_addr, label
ORDER BY occorrenze DESC
LIMIT 5
```

Dalla dashboard è possibile bloccare con un click l'IP attaccante selezionato: il comando viene trasmesso via UDP al demone firewall sul nodo r5 e l'IP viene registrato in MongoDB (`blocked_ips`).

### 7.3 Bilanciamento del Dataset (`bilanciamento.sql`)

**Obiettivo**: analizzare la distribuzione delle classi per valutare lo sbilanciamento del dataset, rilevante in ottica di Machine Learning.

```sql
SELECT Attack AS label, COUNT(*) AS occorrenze
FROM traffico_nids
GROUP BY Attack
```

Il risultato viene visualizzato come **grafico a barre orizzontale** (Altair `mark_bar`) con classi ordinate per frequenza decrescente. Vengono calcolate anche le percentuali di ogni classe sul totale. Un dataset fortemente sbilanciato (dove `Benign` rappresenta la grande maggioranza dei record) porta a modelli di classificazione con alta accuracy ma bassa recall sulle classi di attacco — questa query evidenzia visivamente tale problematica.

### 7.4 Distribuzione dei Protocolli e Porte (`analisi_protocolli.sql`)

**Obiettivo**: identificare quali porte di destinazione e protocolli sono più coinvolti nel traffico, sia benigno che malevolo.

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

Il risultato è un **istogramma a barre impilate** (stacked bar chart Altair): asse Y con le porte più trafficate, asse X con il numero di flussi, colore per classificazione. Permette di identificare immediatamente le porte "calde" (80, 443, 22, 53, 179) e la natura del traffico che le attraversa.

### 7.5 Andamento Temporale del Traffico (`analisi_temporale.sql`)

**Obiettivo**: analizzare l'evoluzione del traffico nel tempo, per identificare picchi e finestre temporali di attività malevola.

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

`date_trunc('minute', ...)` aggrega i flussi in finestre temporali di un minuto; `from_unixtime` converte il timestamp in millisecondi nel formato datetime di Spark. Il grafico è un **line chart multi-serie** (Altair `mark_line`) con una linea per ogni label.

### 7.6 Top Talkers — Matrice Sorgente/Destinazione (`top_talkers.sql`)

**Obiettivo**: individuare le coppie IP (sorgente → destinazione) che generano il maggior volume di traffico.

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

Il risultato è una **heatmap** (Altair `mark_rect`) a matrice IP sorgente × IP destinazione, dove l'intensità del colore (scala `reds`) indica il volume di byte scambiati. È particolarmente efficace per evidenziare attacchi volumetrici, dove uno stesso IP sorgente appare in molte celle della matrice.

---

## 8. Catalogo Dati e Data Lake Explorer

### 8.1 Gestione del Catalogo

La sezione **Catalogo** della dashboard replica le funzionalità di un Data Catalog enterprise:

- **Ricerca full-text** sui campi `name` e `description` tramite regex MongoDB (`$regex` + `$options: "i"`)
- **Stato online/offline** verificato in tempo reale (esistenza file su disco o ping MongoDB)
- **Anteprima dei dati** (prime 10 righe) con statistiche descrittive automatiche per colonne numeriche
- **Schema del dataset** visualizzato in forma tabellare con nome, tipo e descrizione di ogni campo
- **Eliminazione controllata** con doppia conferma e rimozione fisica del file

### 8.2 Upload di Nuovi Dataset con Validazione Multilivello

Il caricamento di CSV implementa una pipeline di validazione **Security by Design**:

1. **Limite dimensione**: rifiuto se > 10 MB
2. **Estensione**: solo `.csv` ammesso
3. **Magic bytes**: rilevamento di file binari mascherati (ELF, PE, PDF, ZIP, PNG, JPEG, GIF…)
4. **Encoding**: verifica UTF-8 o Latin-1
5. **Keyword injection**: blocco se presenti `#!/bin/bash`, `<script>`, `<?php`, `eval(`, `exec(`, ecc.
6. **Struttura CSV**: consistenza del numero di colonne su tutte le righe
7. **Formula injection**: sanitizzazione celle che iniziano con `=`, `+`, `-`, `@` (spreadsheet injection)

Ogni tentativo malevolo viene registrato nell'**Audit Log** (`audit_logs`) con timestamp e motivo del blocco.

---

## 9. Sistema di Sicurezza e Risposta Automatica

Il sistema implementa un **ciclo chiuso di rilevamento e risposta** che collega il traffico live al firewall perimetrale:

```
Sniffer (tcpdump) → PCAP → pcap_ingestor.py → MongoDB (alerts)
                                                       ↓
Dashboard Admin → blocca IP → UDP:5000 → firewall_daemon.py (r5) → iptables
                                                       ↓
                    MongoDB (blocked_ips) ← sync_firewall.py (avvio)
```

Il modulo `pcap_ingestor.py` rileva pattern sospetti nei flussi TCP live:

| Condizione Rilevata | Alert Generato |
|---|---|
| Porta 179 (BGP) | `POSSIBILE BGP HIJACKING` |
| Porta 21 (FTP) | `TENTATIVO FILE INJECTION` |
| Porta 22 (SSH) | `TENTATIVO BRUTE FORCE SSH` |
| Porta 80 (HTTP) da IP esterni | `POSSIBILE DOS/SYN FLOOD` |
| Porta 27017 (MongoDB) da IP esterni | `ACCESSO DATABASE NON AUTORIZZATO` |

Il demone `firewall_daemon.py` su r5 ascolta su UDP/5000 e applica regole `iptables -A FORWARD/INPUT -s <ip> -j REJECT` al gateway perimetrale. Lo script `sync_firewall.py` all'avvio ripristina tutte le regole da MongoDB, garantendo la sopravvivenza al riavvio del container (**state recovery**).

---

## 10. Assistente IA (AI Copilot)

### 10.1 Architettura LLM

Il nodo `llm` ospita un'istanza **Ollama** con accesso GPU (passthrough `NVIDIA_VISIBLE_DEVICES=all`), esposta sulla porta 11434. I modelli sono configurati dinamicamente in MongoDB (collezione `llm_models`), consentendo di aggiungere o rimuovere modelli senza toccare il codice:

| Modello | ID Ollama | Tipo | Caratteristica |
|---|---|---|---|
| Veloce | `llama3.2:3b` | `llama` | Risposte dirette, no reasoning |
| Ragionamento | `qwen3.5:9b` | `qwen` | Reasoning esplicito con `<think>` |

### 10.2 Prompt Engineering

Il prompt di sistema viene caricato da file in `storage/src/prompts/` in base al tipo di modello. Questo disaccoppia la logica applicativa dalla configurazione dei modelli.

**Prompt per il modello di ragionamento (Qwen) — `qwen.txt`:**

```
Sei un assistente virtuale esperto di cybersecurity per il Data Center.
IMPORTANTE: Devi rispondere SEMPRE in lingua ITALIANA.

Linee guida:
1. Esegui sempre una fase di ragionamento preliminare tra i tag <think> e </think>.
2. Pensa in italiano all'interno dei tag <think>.
3. Dopo </think>, scrivi la risposta finale: chiara, professionale e concisa.
4. Usa termini tecnici italiani (es. "regole del firewall", "traffico bloccato").
5. Assisti con analisi del traffico, IP bloccati e allarmi firewall.
```

**Prompt per la generazione SQL — `sql_qwen.txt`:**

```
Sei un assistente esperto in Data Engineering, specializzato in query SQL per Apache Spark.
Regole fondamentali:
1. Restituisci SOLO il codice SQL. Niente testo extra, niente markdown.
2. La query DEVE iniziare con "SELECT" o "WITH".
3. Tabelle disponibili: 'storico_parquet' e 'live_mongo'.
4. 'storico_parquet': IPV4_SRC_ADDR, IPV4_DST_ADDR, PROTOCOL, IN_BYTES, OUT_BYTES, label, Attack, FLOW_START_MILLISECONDS.
5. 'live_mongo': timestamp, src, dst, proto, summary.
Usa <think> per ragionamenti interni; il blocco finale deve essere solo SQL.
```

### 10.3 Streaming e Visualizzazione del Reasoning

Il modulo `llm_utils.py` gestisce la comunicazione con Ollama tramite l'endpoint `/api/generate` in modalità **streaming** (chunked HTTP), con i seguenti parametri:

```python
options_payload = {
    "temperature": 0.3,
    "top_p": 0.85,
    "num_predict": 2048
}
```

Per ogni chunk ricevuto, il modulo separa i token di ragionamento (tag `<think>`) da quelli della risposta finale tramite regex:

```python
t_match = re.search(r'<think>(.*?)(?:</think>|$)', raw_stream, re.DOTALL)
c_answer = re.sub(r'<think>.*?(?:</think>|$)', '', raw_stream, flags=re.DOTALL)
```

I token di **ragionamento** vengono visualizzati in un box separato con sfondo scuro e bordo viola, mentre la **risposta finale** appare nel pannello principale. Un timer mostra il tempo di generazione token per token.

### 10.4 RAG Contestuale (Retrieval-Augmented Generation)

Per le domande riguardanti la sicurezza, l'AI Copilot implementa una forma semplificata di **RAG**: prima di inviare il prompt al modello, il sistema recupera da MongoDB i dati contestuali più rilevanti e li inietta come contesto:

```python
blocked_ips = list(m_client["datalake"]["blocked_ips"]
    .find({"status": "BLOCKED"}).limit(5))
alerts = list(m_client["datalake"]["alerts"]
    .sort("timestamp", -1).limit(5))

prompt_completo = f"""[IMPORTANTE - RISPONDI IN LINGUA ITALIANA]
Usa questi dati reali del Data Center se pertinenti:

IP bloccati nel firewall edge:
{contesto_bloccati}

Allarmi di sicurezza recenti:
{contesto_alert}

Domanda dell'utente: {prompt}"""
```

Il rilevamento del tipo di query (generica vs. di sicurezza) avviene tramite una lista di keyword (`"ip"`, `"bloccat"`, `"firewall"`, `"traffico"`, `"mongo"`, ecc.). I saluti vengono riconosciuti separatamente per non costruire inutilmente il contesto MongoDB.

### 10.5 Generazione SQL via LLM (NL2SQL)

Il **Data Lake Explorer** integra un assistente IA specializzato nella generazione di query Spark SQL. Il prompt di sistema (`sql_qwen.txt`) istruisce il modello a generare esclusivamente codice SQL, specificando le tabelle disponibili e le loro colonne. La risposta viene renderizzata come blocco di codice SQL con syntax highlighting.

---

## 11. Dashboard Amministrativa

La dashboard è sviluppata in **Python/Streamlit** e suddivisa in 5 tab principali:

| Tab | Modulo | Contenuto |
|---|---|---|
| Homepage | `homepage.py` | Stato servizi (MongoDB, Spark, LLM), KPI globali |
| Catalogo | `catalogo.py` | Data Catalog, preview, schema, upload CSV, Data Lake Explorer |
| Analisi | `spark_analysis.py` | 6 tab analitiche con le query Spark SQL descritte nel cap. 7 |
| Sniffer | `live_sniffer.py` | Traffico live da MongoDB, Privacy Mode, download PCAP |
| Assistente IA | `ai_copilot.py` | Chat con LLM locale con RAG contestuale |

### Funzionalità Trasversali

- **Alert banner**: mostra in tempo reale se sono presenti attacchi attivi negli ultimi 5 minuti
- **Auto-refresh**: toggle per il refresh automatico ogni 2 secondi (monitoraggio live)
- **Privacy Mode**: maschera l'ultimo ottetto degli IP (es. `192.168.1.xxx`) in ambienti condivisi
- **Audit Trail**: ogni azione rilevante (blocco IP, upload dataset, interrogazione LLM) viene registrata in `audit_logs` con timestamp, utente e dettaglio
- **Hard Reset Spark**: libera la cache della sessione Spark e riconnette al cluster in caso di disconnessione

---

## 12. Conclusioni

Il progetto ha realizzato una piattaforma Big Data completa che dimostra l'applicazione pratica delle seguenti competenze:

- **Ingestion di dati eterogenei**: combinazione di un dataset storico in formato Parquet (66M+ record) con dati live da cattura PCAP, entrambi accessibili tramite lo stesso layer di query Spark SQL grazie alla Data Federation.
- **Elaborazione distribuita**: Apache Spark ha elaborato oltre 66 milioni di record con query SQL complesse su aggregazioni, window functions temporali e join tra sorgenti dati diverse (Parquet + MongoDB).
- **Visualizzazione analitica**: sei visualizzazioni interattive (barre impilate, line chart multi-serie, heatmap, barre orizzontali) offrono prospettive complementari sul traffico, dalla distribuzione delle classi alla matrice dei flussi tra coppie di IP.
- **Architettura Data Lake**: MongoDB funziona come Data Lake operazionale per i dati live (Capped Collection) mentre Parquet copre l'analisi storica. Il Data Catalog centralizza i metadati di entrambe le sorgenti con schema, posizione e stato online/offline.
- **Integrazione AI**: LLM locali (Qwen 3.5, Llama 3.2) con RAG contestuale su dati MongoDB, prompt engineering separato dal codice e generazione automatica di query SQL (NL2SQL), senza dipendere da servizi cloud esterni.
- **Sicurezza applicata**: ciclo chiuso di risposta agli incidenti dalla rilevazione al blocco firewall, con persistenza su database, meccanismi di audit trail e validazione multilivello dei file caricati.

### Possibili Sviluppi Futuri

- Integrazione di un modello di Machine Learning (Random Forest o XGBoost) addestrato direttamente su Spark MLlib per la classificazione automatica del traffico
- Implementazione di un sistema di alerting proattivo basato su soglie dinamiche calcolate su finestre temporali scorrevoli (Spark Structured Streaming)
- Estensione del Data Lake Explorer con supporto alla scrittura in modalità append per la creazione di report permanenti
- Configurazione multi-worker Spark su nodi distinti per testare lo scaling orizzontale del cluster

---

*Relazione redatta il 11/06/2026*
