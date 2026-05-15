with traffico as (
    select
    
    case
        when l4_dst_port = 179 or l4_src_port = 179 then 'BGP Hijacking/Exploit'
        when l4_dst_port = 22 then 'SSH Brute Force'
        when l4_dst_port = 53 then 'DNS Amplification'
        when l4_dst_port = 80 or l4_dst_port = 443 then 'Web Attack (HTTP/S)'
        when l4_dst_port = 21 then 'FTP File Ingestion Exploit'

        when flow_duration_milliseconds < 100 and in_pkts > 1000 then 'L3/L4 Flood (DDoS)'
        when in_pkts > 5000 and in_bytes > 100000 then 'Volumetric DDoS'

        else 'Altro / Malicious General'
    end as vettore_attacco,

    label as etichetta_dataset,
    count(*) as occorrenze,
    round(avg(flow_duration_milliseconds), 2) as durata_media_flusso,
    round(sum(in_pkts + out_pkts), 0) as pacchetti_totali,
    sum(in_bytes + out_bytes) as traffico_b

    from traffico_nids
    where label != 'Benign'
    group by 1, 2
)

select vettore_attacco,
       etichetta_dataset,
       occorrenze,
       durata_media_flusso,
       pacchetti_totali,
       traffico_b,
       case
            when traffico_b >= 1024.0 * 1024.0 * 1024.0 * 1024.0 then concat(round(traffico_b * 1.0 / (1024.0 * 1024.0 * 1024.0 * 1024.0), 2), 'TB')
            when traffico_b >= 1024.0 * 1024.0 * 1024.0 then concat(round(traffico_b * 1.0 / (1024.0 * 1024.0 * 1024.0), 2), 'GB')
            when traffico_b >= 1024.0 * 1024.0 then concat(round(traffico_b * 1.0 / (1024.0 * 1024.0 ), 2), 'MB')
            when traffico_b >= 1024.0 then concat(round(traffico_b * 1.0 / 1024.0, 2), 'KB')
            else concat(traffico_b, 'B')
        end as traffico_h
from traffico
order by traffico_b desc;
