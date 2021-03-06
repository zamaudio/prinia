from tempfile import NamedTemporaryFile
from subprocess import check_call
import os

import re

from .models import Primer


class Primer3(object):

    def __init__(self, primer3_exe, template, target, excluded_region,
                 opt_prim_length=25, opt_gc_perc=50, min_melting_t=58,
                 max_melting_t=62, min_product_size=200,
                 max_product_size=600):
        self.primer3_exe = primer3_exe
        self.template = template
        self.target = target
        self.excluded_region = excluded_region
        self.opt_prim_length = opt_prim_length
        self.opt_gc_perc = opt_gc_perc
        self.min_melting_t = min_melting_t
        self.max_melting_t = max_melting_t
        self.min_product_size = min_product_size
        self.max_product_size = max_product_size

    @property
    def range(self):
        return "{0}-{1}".format(self.min_product_size, self.max_product_size)

    @property
    def opt_size(self):
        return int(
            self.min_product_size +
            (float((self.max_product_size - self.min_product_size)) / 2)
        )

    def create_config(self, handle):
        """Create config for primer3."""

        cfg_str = "SEQUENCE_ID=example\n" \
                  "SEQUENCE_TEMPLATE={seq}\n" \
                  "SEQUENCE_TARGET={tar}\n" \
                  "SEQUENCE_EXCLUDED_REGION={exc}\n" \
                  "PRIMER_TASK=pick_detection_primers\n" \
                  "PRIMER_PICK_LEFT_PRIMER=1\n" \
                  "PRIMER_PICK_INTERNAL_OLIGO=0\n" \
                  "PRIMER_PICK_RIGHT_PRIMER=1\n" \
                  "PRIMER_MIN_GC=20.0\n" \
                  "PRIMER_INTERNAL_MIN_GC=20.0\n" \
                  "PRIMER_OPT_GC_PERCENT={gc}\n" \
                  "PRIMER_MAX_GC=80.0\n" \
                  "PRIMER_INTERNAL_MAX_GC=80.0\n" \
                  "PRIMER_WT_GC_PERCENT_LT=0.0\n" \
                  "PRIMER_INTERNAL_WT_GC_PERCENT_LT=0.0\n" \
                  "PRIMER_GC_CLAMP=0\n" \
                  "PRIMER_MAX_END_GC=5\n" \
                  "PRIMER_OPT_SIZE={size}\n" \
                  "PRIMER_MIN_SIZE={isize}\n" \
                  "PRIMER_MAX_SIZE={asize}\n" \
                  "PRIMER_MAX_NS_ACCEPTED=0\n" \
                  "PRIMER_PRODUCT_SIZE_RANGE={range}\n" \
                  "PRIMER_PRODUCT_OPT_SIZE={osize}\n" \
                  "PRIMER_PAIR_WT_PRODUCT_SIZE_GT=0.1\n" \
                  "PRIMER_PAIR_WT_PRODUCT_SIZE_LT=0.1\n" \
                  "P3_FILE_FLAG=1\n" \
                  "SEQUENCE_INTERNAL_EXCLUDED_REGION=37,21\n" \
                  "PRIMER_EXPLAIN_FLAG=1\n" \
                  "PRIMER_MIN_TM={it}\n" \
                  "PRIMER_MAX_TM={at}\n" \
                  "PRIMER_NUM_RETURN=200\n" \
                  "=".format(seq=self.template, tar=self.target,
                             exc=self.excluded_region,
                             gc=self.opt_gc_perc,
                             size=self.opt_prim_length,
                             isize=self.opt_prim_length-5,
                             asize=self.opt_prim_length+5,
                             range=self.range,
                             osize=self.opt_size,
                             it=self.min_melting_t,
                             at=self.max_melting_t
                             )

        handle.write(cfg_str)

    def run(self):
        cfg = NamedTemporaryFile(delete=False, mode="w")
        out = NamedTemporaryFile()

        self.create_config(cfg)
        cfg.close()
        args = [self.primer3_exe, "-output", out.name, cfg.name]

        _ = check_call(args)  # noqa

        retval = []
        with open(out.name) as handle:
            for l in handle:
                retval.append(l.strip())

        out.close()
        os.remove(cfg.name)

        return retval


def _parse_single_pair_id(id, lines):
    """Parse single pair id"""
    left_seq_key = "PRIMER_LEFT_{0}_SEQUENCE=".format(id)
    right_seq_key = "PRIMER_RIGHT_{0}_SEQUENCE=".format(id)
    left_pos_key = "PRIMER_LEFT_{0}=".format(id)
    right_pos_key = "PRIMER_RIGHT_{0}=".format(id)
    left_gc_key = "PRIMER_LEFT_{0}_GC_PERCENT".format(id)
    right_gc_key = "PRIMER_RIGHT_{0}_GC_PERCENT".format(id)

    left_seq_line = [x for x in lines if x.startswith(left_seq_key)]
    right_seq_line = [x for x in lines if x.startswith(right_seq_key)]
    left_pos_line = [x for x in lines if x.startswith(left_pos_key)]
    right_pos_line = [x for x in lines if x.startswith(right_pos_key)]
    left_gc_line = [x for x in lines if x.startswith(left_gc_key)]
    right_gc_line = [x for x in lines if x.startswith(right_gc_key)]

    d = {}
    for name, val in zip(
            ["left", "right", "left_gc", "right_gc"],
            [left_seq_line, right_seq_line, left_gc_line, right_gc_line]
    ):
        if len(val) != 1:
            raise ValueError("Value for {n} "
                             "must have exactly one match".format(n=name))
        d[name] = val[0].split("=")[-1]

    for name, val in zip(["left_pos", "right_pos"],
                         [left_pos_line, right_pos_line]):
        if len(val) != 1:
            raise ValueError("Vale for {n} "
                             "must have exactly one match".format(n=name))
        d[name] = val[0].split("=")[-1].split(",")[0]

    return Primer(**d)


def parse_primer3_output(lines):
    """Parse primer3 output to Primers"""
    seq_re = re.compile('^PRIMER_LEFT_(\d+)_SEQUENCE=.+$')

    matches = [seq_re.match(x) for x in lines]
    pair_ids = [int(x.group(1)) for x in matches if x is not None]

    for id in pair_ids:
        yield _parse_single_pair_id(id, lines)
