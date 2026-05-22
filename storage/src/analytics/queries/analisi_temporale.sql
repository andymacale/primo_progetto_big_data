SELECT 
    date_trunc('minute', from_unixtime(FLOW_START_MILLISECONDS / 1000)) as time_window,
    label,
    SUM(IN_BYTES + OUT_BYTES) as total_bytes,
    COUNT(*) as flow_count
FROM traffico_nids
GROUP BY 1, 2
ORDER BY 1 ASC
