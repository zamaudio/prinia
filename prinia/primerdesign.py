"""
This script generates primer pairs from either LOVD input or BED files for
regions.
Output in Miracle XML or TSV
"""

import argparse

from prinia.lovd import var_from_lovd
from prinia.design import get_primer_from_region
from prinia.models import Region
from prinia.miracle_xml import (vars_and_primers_to_xml,
                                regions_and_primers_to_xml)
from prinia.utils import generate_fastq_from_primers, NoPrimersException

__author__ = 'ahbbollen'


def primers_from_lovd(lovd_file, padding, product_size, n_prims, reference,
                      bwa_exe, samtools_exe, primer3_exe, output_bam, dbsnp,
                      field, max_freq, m13=False, m13_f="", m13_r="",
                      strict=False, min_margin=10, ignore_errors=False,
                      **prim_args):
    """**prim_args will be passed on to primer3"""

    variants = var_from_lovd(lovd_file)
    primers = []
    for var in variants:
        region = Region.from_variant(var, padding_l=padding, padding_r=padding)
        try:
            _, prims = get_primer_from_region(region, reference, product_size,
                                              n_prims, bwa_exe, samtools_exe,
                                              primer3_exe,
                                              output_bam=output_bam,
                                              dbsnp=dbsnp, field=field,
                                              max_freq=max_freq, strict=strict,
                                              min_margin=min_margin,
                                              **prim_args)
            primers.append(prims[0])
        except NoPrimersException:
            if ignore_errors:
                continue
            else:
                raise NoPrimersException
    if m13:
        primers = m13_primers(primers, m13_f, m13_r)

    return variants, primers


def primers_from_region(bed_path, padding, product_size, n_prims, reference,
                        bwa_exe, samtools_exe, primer3_exe, output_bam,
                        dbsnp, field, max_freq, m13=False, m13_f="",
                        m13_r="", strict=False, min_margin=10,
                        **prim_args):
    """**prim_args will be passed on to primer3"""
    regions = []
    primers = []
    with open(bed_path, "r") as bed:
        for line in bed:
            if line.startswith("track"):  # ignore tracklines
                continue
            region = Region.from_bed(line, reference, padding_l=padding,
                                     padding_r=padding)
            regs, prims = get_primer_from_region(region, reference,
                                                 product_size, n_prims,
                                                 bwa_exe, samtools_exe,
                                                 primer3_exe,
                                                 output_bam=output_bam,
                                                 dbsnp=dbsnp, field=field,
                                                 max_freq=max_freq,
                                                 strict=strict,
                                                 min_margin=min_margin,
                                                 **prim_args)
            regions += regs
            primers += prims

    if m13:
        primers = m13_primers(primers, m13_f, m13_r)

    return regions, primers


def primers_to_xml(object, primers, xml, type='variants', sample=None):
    if type == 'variants':
        xml_out = vars_and_primers_to_xml(object, primers, xml)
    elif type == 'regions':
        xml_out = regions_and_primers_to_xml(object, primers, xml,
                                             sample=sample)
    else:
        raise ValueError("Wrong type specified")

    with open(xml, "wb") as handle:
        handle.write(xml_out)


def primers_to_tsv(object, primers, tsv, type='variants', sample='NA'):
    with open(tsv, "wb") as handle:
        if type == 'variants':
            header = ['Sample', 'Chromosome', 'Hgvs (genomic)', 'transcript',
                      'hgvs (transcript)', 'fragment', 'forward', 'reverse']
        else:
            header = ['Sample', 'Chr', 'Start', 'Stop', "size", "search_size",
                      'other_information',  'fragment', 'forward', 'reverse']
        headerline = "\t".join(header) + "\n"
        handle.write(headerline.encode())

        for o, prim in zip(object, primers):
            line = []
            if type == 'variants':
                line += [o.miracle_id, o.chromosome, o.variant_on_genome,
                         o.transcript_id_ncbi,
                         o.variant_on_transcript_dna]
            else:
                line += [sample, o.chr, o.start, o.stop, len(o),
                         o.size(padded=True), o.other_information]
            line += [prim.fragment_sequence, prim.left, prim.right]
            linest = "\t".join(map(str, line)) + "\n"
            handle.write(linest.encode())


def m13_primers(primers, m13_for, m13_rev):
    for p in primers:
        p.left = m13_for + p.left
        p.right = m13_rev + p.right

    return primers


def main():
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("-l", "--lovd", help="Input LOVD file")
    group.add_argument('--region', help="Input region file")
    parser.add_argument('-p', '--padding',
                        help="Padding around regions or variants in bases. "
                             "Defaults to 100",
                        type=int, default=100)

    output_group = parser.add_mutually_exclusive_group(required=True)
    output_group.add_argument('-x', '--xml', help="Output Miracle XML file")
    output_group.add_argument('-t', '--tsv', help="Output TSV file")

    parser.add_argument('-b', '--bam',
                        help="Path to output BAM file containing primers",
                        required=True)

    parser.add_argument('-s', '--sample', help="Same ID for regions")

    parser.add_argument('--product_size',
                        help="Size range of desired product. "
                             "Defaults to 200-450. "
                             "This will be taken as a minimum product size in "
                             "the case of regions",
                        default="200-450")
    parser.add_argument("--min-margin", type=int, default=10,
                        help="Minimum distance from region or variant. "
                             "Default = 10")
    parser.add_argument("--strict", help="Enable strict mode. "
                                         "Primers with products larger than "
                                         "max product size will "
                                         "NOT be returned",
                        action="store_true")
    parser.add_argument('--n_raw_primers',
                        help="Legacy option. Will be ignored",
                        default=4, type=int)

    parser.add_argument('--m13', action="store_true",
                        help="Output primers with m13 tails")
    parser.add_argument('--m13-forward', type=str,
                        default="TGTAAAACGACGGCCAGT",
                        help="Sequence of forward m13 tail")
    parser.add_argument('--m13-reverse', type=str,
                        default="CAGGAAACAGCTATGACC",
                        help="Sequence of reverse m13 tail")

    parser.add_argument("-f", "--field",
                        help="Name of field in DBSNP file "
                             "for allele frequency")
    parser.add_argument("-af", "--allele-freq",
                        help="Max accepted allele freq",
                        type=float, default=0.0)

    parser.add_argument("-fq1", type=str, default=None,
                        help="Path to forward fastq file for primer output. "
                             "Set if you want to export your primers in fastq "
                             "format (qualities will be sanger-encoded 40)")
    parser.add_argument("-fq2", type=str, default=None,
                        help="Path to reverse fastq file for primer output. "
                             "Set if you want to export your primers in fastq "
                             "format (qualities will be sanger-encoded 40)")

    parser.add_argument('-R', '--reference',
                        help="Path to reference fasta file",
                        default=None, required=True)
    parser.add_argument('--dbsnp', help="Path to DBSNP vcf",
                        default=None, required=False)
    parser.add_argument('--primer3', help="Path to primer3_core exe",
                        default=None, required=True)
    parser.add_argument('--bwa', help="Path to BWA exe", default="bwa")
    parser.add_argument('--samtools', help="Path to samtools exe",
                        default="samtools")

    parser.add_argument("--ignore-errors", help="Ignore errors",
                        action="store_true")

    parser.add_argument("--opt-primer-length",
                        help="Optimum primer length (default = 25)",
                        type=int, default=25)
    parser.add_argument("--opt-gc-perc",
                        help="Optimum primer GC percentage (default = 50)",
                        type=int, default=50)
    parser.add_argument("--min-melting-temperature",
                        help="Minimum primer melting temperature "
                             "(default = 58)",
                        type=int, default=58)
    parser.add_argument("--max-melting-temperature",
                        help="Maximum primer melting temperature "
                             "(default = 62)",
                        type=int, default=62)

    args = parser.parse_args()

    if not args.lovd and not args.region:
        raise ValueError("Please supply an input file")

    if not args.xml and not args.tsv:
        raise ValueError("Please supply an output file")

    if args.region and not args.sample:
        raise ValueError("Must submit a sample ID")

    if args.field and not args.allele_freq:
        raise ValueError("Must set an allele frequency")

    primers = []
    if args.lovd and args.xml:
        variants, primers = primers_from_lovd(args.lovd, args.padding,
                                              args.product_size,
                                              args.n_raw_primers,
                                              args.reference, args.bwa,
                                              args.samtools, args.primer3,
                                              args.bam, args.dbsnp,
                                              args.field, args.allele_freq,
                                              args.m13, args.m13_forward,
                                              args.m13_reverse,
                                              args.strict,
                                              args.min_margin,
                                              args.ignore_errors)
        primers_to_xml(variants, primers, args.xml, type='variants')

    elif args.region and args.xml:
        regions, primers = primers_from_region(args.region, args.padding,
                                               args.product_size,
                                               args.n_raw_primers,
                                               args.reference, args.bwa,
                                               args.samtools, args.primer3,
                                               args.bam, args.dbsnp,
                                               args.field, args.allele_freq,
                                               args.m13, args.m13_forward,
                                               args.m13_reverse,
                                               args.strict,
                                               args.min_margin)
        primers_to_xml(regions, primers, args.xml, type='regions',
                       sample=args.sample)

    elif args.xml and args.tsv:
        variants, primers = primers_from_lovd(args.lovd, args.padding,
                                              args.product_size,
                                              args.n_raw_primers,
                                              args.reference, args.bwa,
                                              args.samtools, args.primer3,
                                              args.bam, args.dbsnp,
                                              args.field, args.allele_freq,
                                              args.m13, args.m13_forward,
                                              args.m13_reverse,
                                              args.strict,
                                              args.min_margin,
                                              args.ignore_errors)
        primers_to_tsv(variants, primers, args.tsv, type='variants')

    elif args.region and args.tsv:
        regions, primers = primers_from_region(args.region, args.padding,
                                               args.product_size,
                                               args.n_raw_primers,
                                               args.reference, args.bwa,
                                               args.samtools, args.primer3,
                                               args.bam, args.dbsnp,
                                               args.field, args.allele_freq,
                                               args.m13, args.m13_forward,
                                               args.m13_reverse,
                                               args.strict,
                                               args.min_margin)
        primers_to_tsv(regions, primers, args.tsv, type='regions',
                       sample=args.sample)
    else:
        raise ValueError("Something odd happened")

    if args.fq1 and args.fq2:
        generate_fastq_from_primers(primers, args.fq1, args.fq2)


if __name__ == '__main__':
    main()
