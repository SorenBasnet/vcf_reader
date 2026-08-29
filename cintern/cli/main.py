import argparse
import sys
from cintern.vcf.reader import get_vcf_header
from cintern.vcf.samples import get_samples
from cintern.vcf.query import query_region
from cintern.vcf.stats import calc_allele_freq



def main():
    parser = argparse.ArgumentParser(prog="genome", description="C-Intern Platform v0.0.1")
    subparsers = parser.add_subparsers(dest = "subcommand", required = True)

    vcf_parser = subparsers.add_parser("vcf", help = "VCF operations")
    vcf_subparsers = vcf_parser.add_subparsers(dest = "vcf_command", required = True)

    info_p = vcf_subparsers.add_parser("info", help = "View VCF header and basic metadata" )
    info_p.add_argument("file", help = "Path to input VCF file")

    samples_p = vcf_subparsers.add_parser("samples", help="List samples in VCF")
    samples_p.add_argument("file", help="Path to input VCF file")

    query_p = vcf_subparsers.add_parser("query", help="Query VCF by region")
    query_p.add_argument("file", help="Path to input VCF file")
    query_p.add_argument("--region", "-r", required=True, help="Region string (e.g., chr1:100000-200000)")

    stats_p = vcf_subparsers.add_parser("stats", help="Compute allele frequency and statistics")
    stats_p.add_argument("file", help="Path to input VCF file")
    stats_p.add_argument("-o", "--output", help="Output VCF file path")

    args = parser.parse_args()

    if args.subcommand == "vcf":
        if args.vcf_command == "info":
            print(get_vcf_header(args.file))

        elif args.vcf_command == "samples":
            samples = get_samples(args.file)
            print(f"Found {len(samples)} samples: ")
            for s in samples:
                print(f" {s}")

        elif args.vcf_command == "query":
            print(query_region(args.file, args.region))

        elif args.vcf_command == "stats":
            res = calc_allele_freq(args.file, args.output)
            if res:
                print(res)

if __name__ == "__main__":
    main()




