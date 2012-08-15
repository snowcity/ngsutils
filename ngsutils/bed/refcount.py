#!/usr/bin/env python
## category General
## desc Given a number of BED files, calculate the number of samples that overlap regions in a reference BED file
'''
Given a BED file containing genomic regions of interest (reference) and a set
of other BED files (tabix-indexed), calculate how many samples also
contain the region of interest.

Example:
ref           (A)========        (B)============================
sample 1       ---    ----              -----  -- ------   ----
sample 2           ----           ------------
sample 3                                                     -----
sample 4          ----

Would return:
        sample 1        sample 2        sample 3        sample 4        total
ref A      2               1               0               1              3
ref B      4               1               1               0              3

'''

import os
import sys
from ngsutils.support.eta import ETA
import ngsutils.support.ngs_utils
import pysam
import ngsutils.support.stats


def usage():
    print __doc__
    print """\
Usage: bedutils refcount {-ns} ref.bed sample1.bed sample2.bed ...
       bedutils refcount {-ns} ref.bed -group name sample1-1 sample1-2 ...\\
                              -group name sample2-1 sample2-2 ...

Where the sample BED files are Tabix indexed (sample1.bed.tgz.tbi exists).
The sample names are calculated using the names of the files.

The reference BED file shouldn't be Tabix indexed (it is read directly)/

If you have only two sample groups a Fisher Test p-value will be calculated.

Options:
  -ns   Ignore strandedness in counts
"""


def _ref_count(tabix, chrom, start, end, strand=None):
    if chrom not in tabix.contigs:
        return 0

    matches = tabix.fetch(chrom, start, end)
    if not strand:
        return len(list(matches))
    else:
        count = 0
        for match in matches:
            tup = match.split('\t')
            if tup[5] == strand:
                count += 1
        return count


def bed_refcount(refname, group_files, group_names, stranded=True):
    groups = []
    for fnames, name in zip(group_files, group_names):
        samples = ngsutils.support.ngs_utils.filenames_to_uniq([os.path.basename(x) for x in fnames])
        tabix = []
        for fname in fnames:
            tabix.append(pysam.Tabixfile(fname))
        groups.append((name, samples, tabix))

    if len(groups) > 1:
        sys.stdout.write('#\t\t\t\t\t\t')
        for name, samples, tabix in groups:
            sys.stdout.write(name)
            for x in xrange(len(samples) + 1):
                sys.stdout.write('\t')
        sys.stdout.write('\n')

    sys.stdout.write('#chrom\tstart\tend\tname\tscore\tstrand')
    for name, samples, tabix in groups:
        sys.stdout.write('\t')
        sys.stdout.write('\t'.join(samples))
        sys.stdout.write('\tpresent')
    if len(groups) == 2:
        sys.stdout.write('\tfisher p-value\tenriched sample')
    sys.stdout.write('\n')

    with open(refname) as f:
        eta = ETA(os.stat(refname).st_size, fileobj=f)
        for line in f:
            eta.print_status()
            if line[0] != '#':
                cols = line.strip().split('\t')
                sys.stdout.write('\t'.join(cols[:6]))
                group_pres_notpres = []
                for name, samples, tabix in groups:
                    present = 0
                    notpresent = 0

                    for t in tabix:
                        count = _ref_count(t, cols[0], int(cols[1]), int(cols[2]), cols[5] if stranded else None)
                        sys.stdout.write('\t')
                        sys.stdout.write(str(count))
                        if count > 0:
                            present += 1
                        else:
                            notpresent += 1

                    group_pres_notpres.append(present)
                    group_pres_notpres.append(notpresent)
                    sys.stdout.write('\t')
                    sys.stdout.write(str(present))
                if len(groups) == 2:
                    sys.stdout.write('\t')
                    sys.stdout.write(str(ngsutils.support.stats.fisher_test(*group_pres_notpres)))
                    sys.stdout.write('\t')
                    if group_pres_notpres[0] > group_pres_notpres[2]:
                        sys.stdout.write(groups[0][0])
                    else:
                        sys.stdout.write(groups[1][0])

                sys.stdout.write('\n')
        eta.done()


if __name__ == '__main__':
    refname = None
    group_files = []
    stranded = True
    group_names = []
    last = None

    for arg in sys.argv[1:]:
        if arg == '-h':
            usage()
        if last == '-group':
            group_files.append([])
            group_names.append(arg)
            last = None
        elif arg == '-ns':
            stranded = False
        elif not refname and os.path.exists(arg):
            refname = arg
        elif arg == '-group':
            last = arg
        elif os.path.exists(arg) and os.path.exists('%s.tbi' % arg):
            if not group_files:
                group_files.append([])
            group_files[-1].append(arg)
        else:
            print "Bad argument: %s" % arg
            usage()
            sys.exit(1)

    if not refname or not group_files:
        usage()
        sys.exit(1)

    bed_refcount(refname, group_files, group_names, stranded=stranded)