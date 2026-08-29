import subprocess
import sys
from cintern.vcf.index import check_vcf_indexed

def query_region(vcf_file: str, region: str) -> str:


    """
    Query an index file on specific chromosom region
    """
    check_vcf_indexed(vcf_file)

    command = ["bcftools", "view", "-r", region, vcf_file]

    try:

        result = subprocess.run(
                command,
                capture_output = True,
                text = True,
                check = True
                )

        return result.stdout

    except subprocess.CalledProcessError as e:
        print(f"Error querying region '{region}':\n{e.stderr}", file=sys.stderr)
        sys.exit(1)


