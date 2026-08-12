import sqlite3
import pandas as pd 

parquet_file = "variants.parquet"
database_file = "variants.db"

df = pd.read_parquet(parquet_file)

conn = sqlite3.connect(database_file)

df.to_sql("variants", conn, if_exists="replace", index=False)

conn.close()

