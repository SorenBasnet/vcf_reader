import csv 
import random 

def generate_mock_gwas(output_file: str, n_variants: int = 5000) -> str:


    """
    Generate mock result statistics for GWAS
    """

    header = ["CHROM", "POS", "ID", "REF", "ALT", "P", "BETA"]

    with open(output_file, "w", newline="") as f:
        writer = csv.writer(f, delimiter="\t")
        writer.writerow(header)

        for i in range(1, n_variants + 1):
            chrom = str(random.randint(1, 22))
            pos = random.randint(100000, 50000000)
            variant_id = f"rs{random.randint(100000, 999999)}"
            ref = random.choice(["A", "C", "G", "T"])
            alt = random.choice([b for b in ["A", "C", "G", "T"] if b != ref])

            if random.random() < 0.005:
                p_val = 10 ** -random.uniform(5, 12)  # Significant hit (< 1e-5)
            else:
                p_val = random.uniform(0.0001, 1.0)

            beta = round(random.uniform(-0.5, 0.5), 4)
            writer.writerow([chrom, pos, variant_id, ref, alt, f"{p_val:.4e}", beta])

    return output_file
