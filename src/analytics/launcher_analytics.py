from pyspark.sql import SparkSession
from pyspark.sql.utils import AnalysisException
import time

def run_sql_analytics():
    print("Avvio Spark SQL ...")
    
    spark = None

    try:
        spark = SparkSession.builder \
                .appName("DataLake_Analytics") \
                .master("spark://spark-master:7077") \
                .getOrCreate()

        query_path = "/opt/bitnami/spark/src/analytics/queries/rilevamento_anomalie.sql"
        print("Lettura della query ...")

        try:
            with open(query_path, 'r') as file:
                query = file.read()
        except FileNotFoundError:
            print(f"Errore nell'apertura del file {query_path}")

        try:
            print("Apertura del file parquet ...")
            parquet_path = "/opt/bitnami/spark/data/processed/BigFlow-NIDS.parquet"
            df = spark.read.parquet(parquet_path)
            df.createOrReplaceTempView("traffico_nids")
            print("Esecuzione della query ...")
            ris = spark.sql(query)
            ris.show()
        except AnalysisException as e:
            print("Errore di sintassi SQL:")
            print(f"\t{e}")
        except Exception as e:
            print("Errore critico di Spark:")
            print(f"\t{e}")

    except Exception as e:
        print("Errore critico di sistema:")
        print(f"\t{e}")

    finally:
        if spark is not None:
            print("Chiusura di spark ...")
            spark.stop()
            print("Spark chiuso correttamente")

if __name__ == "__main__":
    run_sql_analytics()