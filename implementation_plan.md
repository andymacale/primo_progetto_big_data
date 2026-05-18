# Scalata del Firewall a Livello Data Center (r5)

Ottima intuizione. Bloccare il traffico solo sul `web_server` lascia esposti `spark` e `mongo_db` in caso di attacchi diretti o se l'attaccante conosce i loro IP interni.

Per proteggere l'intero Data Center, **sposteremo il demone firewall sul router di frontiera `r5`**.
`r5` è il gateway di accesso all'intero Data Center. Qualsiasi pacchetto proveniente dall'esterno verso i server interni DEVE passare per `r5`. Bloccandolo qui, creiamo uno scudo invalicabile per tutta l'infrastruttura.

## Modifiche Architetturali

### 1. Spostamento del Demone su `r5`
- Creerò il file `./r5/firewall_daemon.py`. Kathara copierà automaticamente questo file all'interno del nodo `r5` ad ogni riavvio.
- Modificherò il comando `iptables` nel demone in modo che agisca sulla catena **FORWARD** (per bloccare il traffico in transito verso i server) e **INPUT** (per proteggere il router stesso):
  `iptables -A FORWARD -s <IP> -j REJECT --reject-with icmp-port-unreachable`
  `iptables -A INPUT -s <IP> -j REJECT --reject-with icmp-port-unreachable`

### 2. Aggiornamento `r5.startup` [MODIFY]
- Aggiungerò l'avvio in background del demone al boot del router `r5`.

### 3. Ripulitura `web_server.startup` [MODIFY]
- Rimuoverò il demone dal web server, visto che ora non serve più ed è obsoleto.

### 4. Aggiornamento Dashboard e Sync (`app.py` & `sync_firewall.py`) [MODIFY]
- Modificherò l'IP di destinazione dei comandi UDP: invece di puntare al web server (`2.0.0.131`), la dashboard manderà l'ordine di blocco a `10.0.0.1`, che è l'indirizzo interno del router `r5` sulla stessa rete dell'`admin`.

## Verifica (A Caldo)
Dopo la modifica avvierò a caldo il demone su `r5` e tu potrai riprovare il ping o inviare traffico arbitrario verso qualsiasi IP del data center (web server o spark): l'attaccante riceverà sempre un "Port Unreachable" alla radice della rete.

Attendo la tua approvazione per fortificare l'intero Data Center!
