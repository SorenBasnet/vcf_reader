import sqlite3
import pandas as pd

parquet_file = "variants_v2.parquet"
database_file = "variants_v2.db"

df = pd.read_parquet(parquet_file)

conn = sqlite3.connect(database_file)


print(df.head())

print()

columns = df["chromosome"].unique()

for col in columns:
    print(col)

    df_chrom = df[df["chromosome"] == col]

    df.to_sql(f"variant{col}",
              conn,
              if_exists = "replace",
              index = False
              )

conn.close()

