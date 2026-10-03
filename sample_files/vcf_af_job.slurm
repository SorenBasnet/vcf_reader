#!/bin/bash
#SBATCH --job-name=vcf_af_job
#SBATCH --output=./logs/vcf_af_job_%j.out
#SBATCH --error=./logs/vcf_af_job_%j.err
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=04:00:00

echo "Starting job vcf_af_job on host $(hostname) at $(date)"

genome vcf stats sample.vcf.gz -o sample_af.vcf.gz

echo "Job finished at $(date)"
