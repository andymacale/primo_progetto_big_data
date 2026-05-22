SELECT 
    IPV4_SRC_ADDR as source_ip,
    IPV4_DST_ADDR as destination_ip,
    label,
    SUM(IN_BYTES + OUT_BYTES) as total_bytes,
    COUNT(*) as flow_count
FROM traffico_nids
WHERE IPV4_SRC_ADDR IS NOT NULL AND IPV4_DST_ADDR IS NOT NULL
GROUP BY 1, 2, 3
ORDER BY total_bytes DESC
LIMIT 100
