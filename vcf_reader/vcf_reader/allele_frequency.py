import subprocess # allows to run external programs, systems and commands and shell scripts directly from python code

def calc_allele_freq(vcf_file, output_file=None):

    """

    Calculate allele frequency from a VCF file using bcftools.
    Variant wise allele frequency report.

    """

    command = [
            "bcftools",
            "+fill-tags",
            vcf_file,
            "--",
            "-t",
            "AF",
            "-Oz",
            "-o",
            output_file
            ]

    result = subprocess.run(
            command,
            capture_output = True,
            text = True,
            check = True
            )

    return result.stdout





