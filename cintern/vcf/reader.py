import subprocess
import pysam
from pathlib import Path

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


def open_variant_file(path: str | Path) -> pysam.VariantFile:
    path = Path(path)


    if not path.exists():
        raise FileNotFoundError(f"File does not exist in file path : {path}")

    if not path.is_file():
        raise ValueError(f"Path is not a file: {path}")

    try:
        return pysam.VariantFile(str(path))

    except Exception as exc:
        raise ValueError(f"Could not open variant file: {path}") from exc



def test_open_variant_file(sample_vcf):

    with open_variant_file(sample_vcf) as variant_file:
        assert variant_file is not None


#if __name__=="__main__":
#    test_open_variant_file("/Users/sorenbasnet/Documents/Github/vcf_reader/sample_file/JAS_N36.GATK.indel.vcf.gz")






