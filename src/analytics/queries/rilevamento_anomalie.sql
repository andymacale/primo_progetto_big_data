select protocol, label as tipo_traffico, count(*) as conteggio_eventi
from traffico_nids
where label != 'Benign'
group by protocol, label
order by conteggio_eventi desc;