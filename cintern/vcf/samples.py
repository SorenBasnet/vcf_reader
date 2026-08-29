import subprocess

def get_samples(vcf_file: str) -> list[str]:

    result = subprocess.run(
            ["bcftools", "query", "-l", vcf_file],
            capture_output = True,
            text = True,
            check = True
            )

    return result.stdout.strip().splitlines()


