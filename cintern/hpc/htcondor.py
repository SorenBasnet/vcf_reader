import subprocess
import sys
from pathlib import Path

def generate_condor_submit(
    job_name: str,
    command: str,
    cpus: int = 1,
    mem_gb: int = 4,
    disk_gb: int = 10,
    output_dir: str = "./logs"
) -> str:
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    sh_path = f"{job_name}.sh"
    with open(sh_path, "w") as f:
        f.write(f"#!/bin/bash\n{command}\n")
    
    # Make wrapper executable
    Path(sh_path).chmod(0o755)

    sub_content = f"""universe = vanilla
executable = {sh_path}
output = {output_dir}/{job_name}_$(Cluster).out
error = {output_dir}/{job_name}_$(Cluster).err
log = {output_dir}/{job_name}_$(Cluster).log

request_cpus = {cpus}
request_memory = {mem_gb}GB
request_disk = {disk_gb}GB

queue
"""
    sub_path = f"{job_name}.sub"
    with open(sub_path, "w") as f:
        f.write(sub_content)
        
    return sub_path

def submit_condor_job(sub_path: str) -> str:
    try:
        result = subprocess.run(
            ["condor_submit", sub_path],
            capture_output=True,
            text=True,
            check=True
        )
        job_output = result.stdout.strip()
        print(job_output)
        return job_output
    except FileNotFoundError:
        print("Error: 'condor_submit' command not found. Ensure you are on a CHTC submit node.", file=sys.stderr)
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        print(f"Error submitting HTCondor job:\n{e.stderr}", file=sys.stderr)
        sys.exit(1)
