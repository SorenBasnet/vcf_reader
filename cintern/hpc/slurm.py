import subprocess
import sys
from pathlib import Path

def generate_slurm_script(job_name: str,command: str,cpus: int = 4,
    mem_gb: int = 16,time_limit: str = "04:00:00",output_dir: str = "./logs") -> str:

    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    script_content = f"""#!/bin/bash
#SBATCH --job-name={job_name}
#SBATCH --output={output_dir}/{job_name}_%j.out
#SBATCH --error={output_dir}/{job_name}_%j.err
#SBATCH --cpus-per-task={cpus}
#SBATCH --mem={mem_gb}G
#SBATCH --time={time_limit}

echo "Starting job {job_name} on host $(hostname) at $(date)"

{command}

echo "Job finished at $(date)"
"""
    script_path = f"{job_name}.slurm"
    with open(script_path, "w") as f:
        f.write(script_content)
    
    return script_path

def submit_slurm_job(script_path: str) -> str:
    try:
        result = subprocess.run(
            ["sbatch", script_path],
            capture_output=True,
            text=True,
            check=True
        )
        job_output = result.stdout.strip()
        print(job_output)
        return job_output
    except FileNotFoundError:
        print("Error: 'sbatch' command not found. Ensure you are on a SLURM submit node.", file=sys.stderr)
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        print(f"Error submitting SLURM job:\n{e.stderr}", file=sys.stderr)
        sys.exit(1)

                
