import argparse

parser = argparse.ArgumentParser(description="Command Line Interface for interacting with automated vcf_reader pipeline")

args = parser.parse_args()

if args.command == "man":
    print(f"Welcome to vcf_reader pipeline ! \
            Here is the manual :\
            1) man - manual\
            2) process - command to process vcf file" \
          )


