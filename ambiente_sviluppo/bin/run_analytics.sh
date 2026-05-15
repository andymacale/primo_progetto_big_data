#!/bin/bash

# Trova dinamicamente il container Spark Master di Kathara
SPARK_CONTAINER=$(docker ps -q --filter "name=spark" | head -n 1)

if [ -z "$SPARK_CONTAINER" ]; then
    echo "ERRORE: Container Spark non trovato. Il lab è avviato?"
    exit 1
fi

echo "Invio del job di Analytics al cluster Spark ($SPARK_CONTAINER)..."

# Percorso locale per il controllo dell esistenza (mappato in /opt/spark/data nel container)
PARQUET_DIR="./storage/data/processed/BigFlow-NIDS.parquet"

if [ ! -d "$PARQUET_DIR" ]; then
    echo "ATTENZIONE: Dati Parquet non trovati in $PARQUET_DIR."
    echo "Avvio la fase di Ingestione nel container..."
    
    docker exec -u root -it $SPARK_CONTAINER \
        /opt/spark/bin/spark-submit /opt/spark/src/ingestion/spark_ingest.py
      
    echo "Ingestione completata!"
else
    echo "Dati Parquet trovati!"
fi

echo "Avvio Analytics..."
docker exec -u root \
  -e PYSPARK_PYTHON=python3 \
  -e PYSPARK_DRIVER_PYTHON=python3 \
  -it $SPARK_CONTAINER \
  /opt/spark/bin/spark-submit \
  --jars $(echo /opt/spark/src/jars/*.jar | tr ' ' ',') \
  --conf spark.jars.ivy=/tmp/.ivy2 \
  /opt/spark/src/analytics/launcher_analytics.py

echo "Esecuzione completata"