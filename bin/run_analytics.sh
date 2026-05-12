#!/bin/bash

echo "Invio del job di Analytics al cluster Spark..."
PARQUET_DIR="./data/processed/BigFlow-NIDS.parquet"

if [ ! -d "$PARQUET_DIR" ]; then
    echo "ATTENZIONE: Dati Parquet non trovati."
    echo "Avvio la fase di Ingestione per convertire il CSV grezzo..."
    
    docker exec \
      -u root \
      -it datalake-spark-master \
      spark-submit \
      --conf spark.hadoop.fs.permissions.umask-mode=000 \
      /opt/bitnami/spark/src/ingestion/spark_ingest.py
      
    echo "Ingestione completata! Dati pronti per l'analisi."
else
    echo "Dati Parquet trovati! Salto la fase di ingestione."
fi

docker exec \
  -u root \
  -e HOME=/tmp \
  -it datalake-spark-master \
  spark-submit \
  --conf spark.jars.ivy=/tmp/.ivy2 \
  /opt/bitnami/spark/src/analytics/launcher_analytics.py

echo "Esecuzione completata"