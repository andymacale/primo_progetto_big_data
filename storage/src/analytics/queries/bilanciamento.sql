select Attack as label, count(*) as occorrenze 
from traffico_nids 
group by Attack