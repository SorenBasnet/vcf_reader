import argparse
import sys
from cintern.vcf.reader import get_vcf_header
from cintern.vcf.samples import get_samples
from cintern.vcf.query import query_region
from cintern.vcf.stats import calc_allele_freq
from cintern.hpc.slurm import generate_slurm_script, submit_slurm_job
from cintern.hpc.htcondor import generate_condor_submit, submit_condor_job
from cintern.publish.manifest import create_gwas_repository
from cintern.publish.report import generate_web_report
from cintern.mock_gwas.mock import generate_mock_gwas


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

    # --- HPC SUBCOMMANDS ---
    hpc_parser = subparsers.add_parser("hpc", help="Submit platform workloads to HPC schedulers")
    hpc_subparsers = hpc_parser.add_subparsers(dest="hpc_command", required=True)

    # genome hpc submit --scheduler slurm --job-name my_stats --cmd "genome vcf stats sample.vcf.gz -o out.vcf.gz"
    submit_p = hpc_subparsers.add_parser("submit", help="Submit a job to SLURM or HTCondor")
    submit_p.add_argument("--scheduler", choices=["slurm", "condor"], default="slurm", help="HPC Scheduler type")
    submit_p.add_argument("--job-name", required=True, help="Name for the HPC job")
    submit_p.add_argument("--cmd", required=True, help="Command string to run on worker node")
    submit_p.add_argument("--cpus", type=int, default=4, help="CPUs to request")
    submit_p.add_argument("--mem", type=int, default=16, help="RAM in GB to request")

    publish_p = subparsers.add_parser("publish", help="Publish GWAS analysis into a web repository")
    publish_p.add_argument("--dir", required=True, help="Target repository directory")
    publish_p.add_argument("--title", required=True, help="Dataset Title")
    publish_p.add_argument("--author", required=True, help="Author Name")
    publish_p.add_argument("--gwas", required=True, help="Path to GWAS output file")
    publish_p.add_argument("--trait", required=True, help="Trait analyzed")
    publish_p.add_argument("--n-samples", type=int, required=True, help="Sample size")

    # Subcommand parser for GWAS
    gwas_parser = subparsers.add_parser("gwas", help="GWAS analysis and utilities")
    gwas_subparsers = gwas_parser.add_subparsers(dest="gwas_command", required=True)

    mock_p = gwas_subparsers.add_parser("mock", help="Generate mock summary stats for testing")
    mock_p.add_argument("-o", "--output", default="mock_gwas.tsv", help="Output file path")
    mock_p.add_argument("-n", "--num-variants", type=int, default=5000, help="Number of variants")


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

    # Route HPC
    elif args.subcommand == "hpc":
        if args.hpc_command == "submit":
            if args.scheduler == "slurm":
                script = generate_slurm_script(
                    job_name=args.job_name,
                    command=args.cmd,
                    cpus=args.cpus,
                    mem_gb=args.mem
                )
                print(f"Generated SLURM script: {script}")
                submit_slurm_job(script)
            elif args.scheduler == "condor":
                sub_file = generate_condor_submit(
                    job_name=args.job_name,
                    command=args.cmd,
                    cpus=args.cpus,
                    mem_gb=args.mem
                )
                print(f"Generated HTCondor submit file: {sub_file}")
                submit_condor_job(sub_file)

    elif args.subcommand == "publish": 
        manifest = create_gwas_repository(
                repo_dir = args.dir, 
                title = args.title, 
                description = "GWAS results platform deployment", 
                author = args.author, 
                gwas_file = args.gwas,
                trait = args.trait, 
                sample_size = args.n_samples
                )

        report_file = generate_web_report(args.dir, args.gwas)
   
        print(f"Repository initialized successfully at: {args.dir}")
        print(f"Manifest written to: {args.dir}/cintern_repo.json")
        print(f"Web viewer created: {report_file}")

    elif args.subcommand == "gwas":
        if args.gwas_command == "mock":
            out = generate_mock_gwas(args.output, args.num_variants)
            print(f"Generated test GWAS summary stats: {out}")

if __name__ == "__main__":
    main()




