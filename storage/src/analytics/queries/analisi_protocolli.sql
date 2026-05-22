SELECT 
    L4_DST_PORT as port,
    CASE 
        WHEN PROTOCOL = 6 THEN 'TCP'
        WHEN PROTOCOL = 17 THEN 'UDP'
        WHEN PROTOCOL = 1 THEN 'ICMP'
        ELSE CAST(PROTOCOL AS STRING)
    END as protocol_name,
    label,
    COUNT(*) as flow_count,
    AVG(IN_BYTES + OUT_BYTES) as avg_bytes
FROM traffico_nids
GROUP BY 1, 2, 3
ORDER BY flow_count DESC
LIMIT 50
