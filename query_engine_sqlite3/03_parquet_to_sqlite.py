import sqlite3
import pandas as pd

parquet_file = "variants_v2.parquet"
database_file = "variants_v2.db"

df = pd.read_parquet(parquet_file)

conn = sqlite3.connect(database_file)

df.to_sql(
    "variants",
    conn,
    if_exists="replace",
    index=False
)

conn.close()

