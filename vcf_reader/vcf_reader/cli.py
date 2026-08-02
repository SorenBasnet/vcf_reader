import argparse

def main():
    parser = argparse.ArgumentParser(
            description="Command Line Interface for interacting with automated VCF reader pipeline"
            )

    parser.add_argument(
            "--man",
            action="store_true",
            help="Show the manual"
            )

    args = parser.parse_args()


    if len(vars(args)) == 1:
        print("""
        Welcome to vcf_reader pipelie v.0.1.0

        ==============================================

        Contact : basnetsoren01@gmail.com

              """)


    elif args.man:
        print("""
        Welcome to vcf_reader pipeline !

        Commands:

            --man       Show manual
            --process   Process VCF files
            --output    Shows output for the file

            """)





if __name__ == "__main__":
    main()
