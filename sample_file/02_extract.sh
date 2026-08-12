#!/bin/bash 

bcftools query \
  -f '%CHROM\t%POS\t%ID\t%REF\t%ALT\t%QUAL\t%FILTER\n' \
  JAS_N36.GATK.indel.vcf.gz > variants.tsv
