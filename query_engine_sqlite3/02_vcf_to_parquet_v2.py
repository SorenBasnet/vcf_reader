import pandas as pd

input_file = "variants_v2.tsv"
output_file = "variants_v2.parquet"

columns = [
    "chromosome",
    "position",
    "variant_id",
    "ref",
    "alt",
    "quality",
    "filter",
    "ac",
    "af",
    "an",
    "dp",
    "mq",
    "qd",
    "fs",
    "sor",
    "baseq_rank_sum",
    "mq_rank_sum",
    "read_pos_rank_sum"
]

df = pd.read_csv(input_file,sep="\t",names=columns,na_values=[".", "NA"])

# Numeric columns
numeric_columns = [
    "position",
    "quality",
    "ac",
    "af",
    "an",
    "dp",
    "mq",
    "qd",
    "fs",
    "sor",
    "baseq_rank_sum",
    "mq_rank_sum",
    "read_pos_rank_sum"
]

for col in numeric_columns:
    df[col] = pd.to_numeric(df[col], errors="coerce")

df.to_parquet( output_file, index=False )
