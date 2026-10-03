from vcf.reader import open_variant_file

def test_open_variant_file(sample_vcf):

    with open_variant_file(sample_vcf) as variant_file:
        assert variant_file is not None


if __name__=="__main__":
    test_open_variant_file("/Users/sorenbasnet/Documents/Github/vcf_reader/sample_file/JAS_N36.GATK.indel.vcf.gz")


