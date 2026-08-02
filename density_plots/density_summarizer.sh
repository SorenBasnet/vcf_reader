!/bin/bash 

# TODO : Install bcftools 
# TODO : probably need to make the fields like CHROM, POS more adjustable 

for file in ;
do 
	bcftools query \
		-f '%CHROM\t%POS\n' \
		$file >> $OUTPUT_FILE

	rm -f $file
done 


