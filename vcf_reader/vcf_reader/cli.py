import argparse
import subprocess
import sys
from .sql import sql_shell

def main():
    parser = argparse.ArgumentParser(
                      description="Command Line Interface for inter\
                                   acting with automated VCF reader \
                                   pipeline"
            )

    parser.add_argument(
            "--man",
            action="store_true",
            help="Show the manual"
            )

    parser.add_argument(
            "-f", "--file",
            type=str,
            help="Path to the input VCF file"
            )

    parser.add_argument(
            "--proceed", "-p",
            type=str,
            help="Process with operating the file in the SLURM and \
                  output value in the server space"
            )

    parser.add_argument(
            "--publish", "--pub",
            type=str,
            help="Publish the results"
            # TODO : think about privacy, where to publish, what files to publish, etc
            )


    subparsers = parser.add_subparsers(dest="command")

    #SQL command
    subparsers.add_parser(
            "sql",
            help = "Enter interactive SQL mode"
            )

    args = parser.parse_args()

    if args.command == "sql":
        sql_shell()
    else:
        parser.print_help()


    if len(vars(args)) == 1:

        print("""
        Welcome to vcf_reader pipelie v.0.1.0

        ==============================================

        Contact : basnetsoren01@gmail.com

        """)

        parser.print_help()
        sys.exit(0)


    elif args.man:
        print("""
        Welcome to vcf_reader pipeline !

        Commands:

            --man       Show manual
            --process   Process VCF files
            --output    Shows output for the file

            """)

    elif args.file:
        print(f"Reading VCF file from:{args.file}")
        header(args.file)


def header(vcf_file):
    result = subprocess.run(
         ["bcftools", "view", "-h", vcf_file],
        capture_output=True,
        text=True,
        check=True
    )

    print(result.stdout)


if __name__ == "__main__":
    main()
