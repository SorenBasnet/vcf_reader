#!/bin/bash 

# Script to extract fields for the sqlite db schema 

bcftools query \
  -f '%CHROM\t%POS\t%ID\t%REF\t%ALT\t%QUAL\t%FILTER\t%INFO/AC\t%INFO/AF\t%INFO/AN\t%INFO/DP\t%INFO/MQ\t%INFO/QD\t%INFO/FS\t%INFO/SOR\t%INFO/BaseQRankSum\t%INFO/MQRankSum\t%INFO/ReadPosRankSum\n' \
  ../sample_file/JAS_N36.GATK.indel.vcf.gz > variants_v2.tsv

