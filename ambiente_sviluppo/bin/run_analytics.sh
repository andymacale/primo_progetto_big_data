#!/bin/bash

echo "Invio del job di Analytics al cluster Spark..."

PARQUET_DIR="./data/processed/BigFlow-NIDS.parquet"

if [ ! -d "$PARQUET_DIR" ]; then
    echo "ATTENZIONE: Dati Parquet non trovati."
    echo "Avvio la fase di Ingestione..."
    
    docker exec -u root -it datalake-spark-master \
        /opt/spark/bin/spark-submit /opt/spark/src/ingestion/spark_ingest.py
      
    echo "Ingestione completata!"
else
    echo "Dati Parquet trovati!"
fi

echo "Avvio Analytics..."
docker exec -u root \
  -e PYSPARK_PYTHON=python3 \
  -e PYSPARK_DRIVER_PYTHON=python3 \
  -it datalake-spark-master \
  /opt/spark/bin/spark-submit \
  --packages org.mongodb.spark:mongo-spark-connector_2.12:10.3.0 \
  --conf spark.jars.ivy=/tmp/.ivy2 \
  /opt/spark/src/analytics/launcher_analytics.py

echo "Esecuzione completata"