#!/bin/bash

# This file will be used to obtain the grch version of the vcf file 

bcftools view -h JAS_N36.GATK.indel.vcf.gz | grep -Ei 'reference|assembly|GRCh|hg19|hg38'


bcftools view -h JAS_N36.GATK.indel.vcf.gz | head -30


bcftools query -f '%CHROM\n' JAS_N36.GATK.indel.vcf.gz | head
