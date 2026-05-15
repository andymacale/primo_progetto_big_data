from pyspark.sql import SparkSession
from pyspark.sql.utils import AnalysisException
import time

def run_sql_analytics():
    print("Avvio Spark SQL ...")
    
    spark = None

    try:
        spark = SparkSession.builder \
            .appName("DataLake_Analytics") \
            .master("spark://spark.cyber.net:7077") \
            .config("spark.mongodb.write.connection.uri", "mongodb://mongo.cyber.net:27017") \
            .getOrCreate()

        query_path = "/opt/spark/src/analytics/queries/rilevamento_anomalie.sql"
        print("Lettura della query ...")

        try:
            with open(query_path, 'r') as file:
                query = file.read()
        except FileNotFoundError:
            print(f"Errore nell'apertura del file {query_path}")

        try:
            print("Apertura del file parquet ...")
            parquet_path = "/opt/spark/data/processed/BigFlow-NIDS.parquet"
            df = spark.read.parquet(parquet_path)
            df.createOrReplaceTempView("traffico_nids")
            print("Esecuzione della query ...")
            ris = spark.sql(query)
            ris.show(truncate=False)
        except AnalysisException as e:
            print("Errore di sintassi SQL:")
            print(f"\t{e}")
        except Exception as e:
            print("Errore critico di Spark:")
            print(f"\t{e}")

        if ris:
            print("Salvataggio su MongoDB ...")
            try:
                ris.write \
                    .format("mongodb") \
                    .mode("overwrite") \
                    .option("connection.uri", "mongodb://mongo.cyber.net:27017") \
                    .option("database", "cyber_reports") \
                    .option("collection", "nids_summary") \
                    .save()
                print("Salvataggio su MongoDB riuscito (Database: cyber_reports, Collection: nids_summary)")

            except Exception as e:
                print("Errore durante il salvataggio su MongoDB")
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