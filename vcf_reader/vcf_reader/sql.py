

def sql_shell():

    print("vcf_reader SQL v0.0.1")
    print("Type EXITSQL to exit. \n")

    while True:
        command = input("SQL> ")

        if command.strip().upper() == "EXITSQL":
            print("Exiting SQL.")
            break

        # Send command to SQL engine
        result = execute_sql(command)

        print(result)


