import subprocess

def get_vcf_header(vcf_file: str) -> str:
    result = subprocess.run(
            ["bcftools", "view", "-h", vcf_file],
            capture_output = True,
            text = True,
            check = True
            )

    return result.stdout


def get_vcf_info(vcf_file: str) -> dict:

    header_text = get_vcf_header(vcf_file)

    return {
            "file" : vcf_file,
            "header_lines": len(header_text.splitlines())
            }


