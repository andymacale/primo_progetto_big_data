from pyspark.sql import SparkSession
import time

def run_sql_analytics():
    print("Avvio Spark SQL ...")
    
    spark = None

    try:
        spark = SparkSession.builder \
            .appName("DataLake_Ingestion") \
            .master("spark://spark-master:7077") \
            .config("spark.hadoop.fs.permissions.umask-mode", "000") \
            .config("spark.speculation", "false") \
            .getOrCreate()

        csv_path = "/opt/bitnami/spark/data/raw/BigFlow-NIDS.csv"
        output_path = "/opt/bitnami/spark/data/processed/BigFlow-NIDS.parquet"

        try:
            start_time = time.time()

            print(f" Lettura del file CSV {csv_path} ...")
            df = spark.read.option("header", "true") \
               .option("inferSchema", "true") \
               .option("samplingRatio", "0.1") \
               .csv(csv_path)

            df = df.withColumn("label", df["label"].cast("string"))

            print(f"Scrittura in formato Parquet in corso ...")
            df.write.mode("overwrite").parquet(output_path)

            end_time = time.time()
            print(f"Ingestione completata in {round(end_time - start_time, 2)} secondi!")

        except Exception as e:
            print(f"ERRORE durante l'ingestione: {e}")

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