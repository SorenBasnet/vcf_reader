import subprocess
import sys
from cintern.vcf.index import check_vcf_indexed

def calc_allele_freq(vcf_file: str, output_file: str = None) -> str:
    # Ensure index exists before processing
    check_vcf_indexed(vcf_file)

    # General options go BEFORE the '--' separator
    command = ["bcftools", "+fill-tags", vcf_file]

    if output_file:
        command.extend(["-Oz", "-o", output_file])

    # Plugin-specific options go AFTER the '--' separator
    command.extend(["--", "-t", "AF"])

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"Error calculating stats for '{vcf_file}':\n{e.stderr}", file=sys.stderr)
        sys.exit(1)

