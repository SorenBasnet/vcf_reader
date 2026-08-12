import pandas as pd

input_file = "variants.tsv"
output_file = "variants.parquet"

cols = [
        "chromosome",
        "position",
        "variant_id",
        "ref",
        "alt",
        "quality",
        "filter"
       ]

df = pd.read_csv(input_file, sep="\t",names=cols)

df.to_parquet(output_file,index=False)

print(df.head())
print(f"\nVariants: {len(df):,}")
print(f"Saved to: {output_file}")
