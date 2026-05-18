select ipv4_src_addr as ip_attaccante,
       count(*) as occorrenze,
       sum(in_bytes + out_bytes) as traffico_b,
       label as classe
from traffico_nids
where label != 'Benign'
group by ipv4_src_addr, label
order by occorrenze desc
limit 5;
