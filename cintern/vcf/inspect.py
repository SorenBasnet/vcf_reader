from pathlib import Path
from cintern.vcf.reader import open_variant_file

"""
This program is strictly to read the
vcf file and yeild the output containing
file info
"""


def inspect_variant_file(path: str|Path) -> dict:

    path = Path(path)

    with open_variant_file(path) as variant_file:

        header = variant_file.header
        first_record = next(iter(variant_file), None)

        return {
            "path": str(path),
            "size_bytes": path.stat().st_size,
            "samples": list(header.samples),
            "contigs": list(header.contigs),
            "info_fields": list(header.info),
            "format_fields": list(header.formats),
            "filter_fields": list(header.filters),
            "first_record": {
            "contig": first_record.contig,
            "position": first_record.pos,
            "reference": first_record.ref,
            "alternates": list(first_record.alts or []),
            } if first_record else None,
        }




