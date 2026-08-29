import os
import subprocess
import sys

def check_vcf_indexed(vcf_file: str) -> None:
    """
    Check if an VCF index file exists(.csi, .tbi), else make a new one
    """

    csi_index = f"{vcf_file}.csi"
    tbi_index = f"{vcf_file}.tbi"

    if os.path.exists(csi_index) or os.path.exists(tbi_index):
        return

    print(f"Index file not found. Generating index file", file=sys.stderr)


    try:
        subprocess.run(["bcftools", "index", vcf_file],
                       capture_output = True,
                       text = True,
                       check = True
                       )

        print("Index successfully generated.", file = sys.stderr)

    except subprocess.CalledProcessError as e :
        print(f"Failed to generate index for '{vcf_file}':\n{e.stderr}", file=sys.stderr)
        sys.exit(1)

