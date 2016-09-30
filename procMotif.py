#!/usr/bin/python

__author__ = "Donghoon Lee"
__copyright__ = "Copyright 2016, Gerstein Lab"
__credits__ = ["Donghoon Lee"]
__license__ = "GPL"
__version__ = "1.0.0"
__maintainer__ = "Donghoon Lee"
__email__ = "donghoon.lee@yale.edu"

from Bio import motifs, SeqIO
from Bio.Seq import Seq
from Bio.Alphabet import IUPAC, generic_dna
import math, collections, ConfigParser, glob, re
import numpy as np
from os import listdir
from os.path import isfile, join
# from subprocess import check_output
# from fractions import gcd

### LOAD CONFIG ###

Config = ConfigParser.ConfigParser()
Config.read("config.ini")

C_PSEUDOCOUNTS = float(Config.get("param","C_PSEUDOCOUNTS"))
C_BACKGROUND_A = float(Config.get("param","C_BACKGROUND_A"))
C_BACKGROUND_C = float(Config.get("param","C_BACKGROUND_C"))
C_BACKGROUND_G = float(Config.get("param","C_BACKGROUND_G"))
C_BACKGROUND_T = float(Config.get("param","C_BACKGROUND_T"))
C_BACKGROUND = {'A':C_BACKGROUND_A,'C':C_BACKGROUND_C,'G':C_BACKGROUND_G,'T':C_BACKGROUND_T}
C_PRECISION = int(Config.get("param","C_PRECISION"))

###

def listOnlyFiles(path):
    return [f for f in listdir(path) if isfile(join(path, f))]

def ls(path):
    return glob.glob(path)

def grep(pattern, file):
    output = []
    with open(file) as f:
        for line in f.readlines():
            if re.search(pattern, line, re.IGNORECASE):
                output.append(line.rstrip())
    return output

def findMatchedPeak(cell, rawTF):
    for filepath in ls(Config.get("data","peak_bed")+'/*.bed'):
        filename = filepath.rstrip().split("/")[-1]
        filename_split = filename.rstrip().split("_")
        if filename_split[4] == cell and filename_split[5] == rawTF:
            print "Found",filename,"for TF:",parseTF(filename_split[5])

###

def get_jaspar_motif(tfName):
    with open(Config.get("data","pfm_db_jaspar")) as handle:
        for m in motifs.parse(handle, "jaspar"):
            if str(m.name).upper() == str(tfName).upper():
                return m
    # if not found
    return None

def parseJaspar(tfName):
    m = get_jaspar_motif(tfName)
    if m == None:
        return None # stop if not found
    writePFM(m)
    writePPM(m,C_PSEUDOCOUNTS)
    writePWM(m,C_PSEUDOCOUNTS,C_BACKGROUND)
    return m

def parseTF(rawName):
    return rawName.rstrip().split("-")[-1]

def writePFM(m):
    with open("MOTIF_"+str(m.name).upper()+".pfm", "w") as output:
        for nt in ['A','C','G','T']:
            for x in m.counts[nt]:
                output.write(str(int(x))+" ")
            output.write("\n")

def writePPM(m):
    ppm = m.counts.normalize(pseudocounts=C_PSEUDOCOUNTS)
    with open("MOTIF_"+str(m.name).upper()+".ppm", "w") as output:
        for nt in ['A','C','G','T']:
            for x in ppm[nt]:
                output.write(str(round(x,3))+" ")
            output.write("\n")

def writePWM(m):
    ppm = m.counts.normalize(pseudocounts=C_PSEUDOCOUNTS)
    pwm = ppm.log_odds(background=C_BACKGROUND)
    with open("MOTIF_"+str(m.name).upper()+".pwm", "w") as output:
        for nt in ['A','C','G','T']:
            for x in pwm[nt]:
                output.write(str(round(x,3))+" ")
            output.write("\n")

def pwm2scaled_pwm(m, pwm):

    ###
    ### scale raw PWM scores ###
    ###

    # copy to np matrix
    scaled_pwm = np.zeros(shape=(4,len(m)))
    for i, nt in enumerate(['A','C','G','T']):
        scaled_pwm[i] = pwm[nt]

    # subtract by min PWM score, to make non-negative matrix
    scale_const = np.min(scaled_pwm)
    nonneg_pwm = scaled_pwm - scale_const

    # scale PWM to range from 0 to C_PRECISION
    scale_factor = (C_PRECISION/np.max(nonneg_pwm))
    scaled_pwm = nonneg_pwm * scale_factor

    # round to nearest integer
    scaled_pwm = np.rint(scaled_pwm).astype(int)

    return scaled_pwm

def scaled_pwm2scoredist(m, scaled_pwm):

    ###
    ### score distribution
    ###

    score_distribution = np.zeros(shape=(len(m),len(m)*C_PRECISION), dtype=np.int)
    print np.shape(score_distribution)

    ### proc tf motif
    # init first row
    for i, nt in enumerate(['A','C','G','T']):
        score_distribution[0,scaled_pwm[i,0]] += 1
    # rest of motif
    for j in range(1,len(m)): ### j: 1 to length of motif
        # print "MOTIF pos:", j
        for k in scaled_pwm[:,j]:
            for idx, count in enumerate(score_distribution[j-1,:]):
                if count > 0:
                    score_distribution[j,idx+k] += count
    return score_distribution

def pwm2pval(motifName, seq):

    with open("pfm_vertebrates.txt") as handle:
        for m in motifs.parse(handle, "jaspar"):
            if str(m.name).upper() == str(motifName).upper():
                ppm = m.counts.normalize(pseudocounts=C_PSEUDOCOUNTS)
                pwm = ppm.log_odds(background=C_BACKGROUND)
                writePWM(m)
                break ### stop if motif is found
    print "PWM:"
    print pwm

    ### scale raw PWM scores
    scaled_pwm = np.zeros(shape=(4,len(m)))

    for i, nt in enumerate(['A','C','G','T']):
        scaled_pwm[i] = pwm[nt]
    # print scaled_pwm

    # subtract by min PWM score, to make non-negative matrix
    scale_const = np.min(scaled_pwm)
    nonneg_pwm = scaled_pwm - scale_const

    # scale
    scale_factor = (C_PRECISION/np.max(nonneg_pwm))
    scaled_pwm = nonneg_pwm * scale_factor

    # round to nearest integer
    scaled_pwm = np.rint(scaled_pwm).astype(int)

    print "Scaled PWM:"
    print scaled_pwm

    ### score distribution
    score_distribution = np.zeros(shape=(len(m),len(m)*C_PRECISION), dtype=np.int)
    print np.shape(score_distribution)
    # init first row
    for i, nt in enumerate(['A','C','G','T']):
        score_distribution[0,scaled_pwm[i,0]] += 1
    # print "first row:",score_distr[0,:]

    # proc rest of motif
    for j in range(1,len(m)): ### j: 1 to length of motif
        print "MOTIF pos:", j
        for k in scaled_pwm[:,j]:
            for idx, count in enumerate(score_distribution[j-1,:]):
                if count > 0:
                    score_distribution[j,idx+k] += count

    scaled_score = int(seq2score(seq,scaled_pwm))
    raw_score = seq2score(seq,pwm)
    print "scaled score:",scaled_score
    print "raw score:",raw_score
    pval = score2pval(scaled_score, score_distribution)
    print "pval:",pval

def seq2score(seq, pwm):
    score = 0.0
    seq2idx = {'A':0, 'C':1, 'G':2, 'T':3}
    for idx, nt in enumerate(seq):
        score += pwm[seq2idx[nt.upper()], idx]
    return score

def score2pval(scaled_score, score_distribution):
    return float(sum(score_distribution[-1,scaled_score:])) / float(math.pow(4,len(score_distribution)))

def pval2score(pval, score_distribution):
    cumsum = 0
    for idx, count in reversed(list(enumerate(score_distribution[-1,:]))):
        cumsum += count
        if float(cumsum) / float(math.pow(4,len(score_distribution))) > pval:
            # print float(cumsum) / float(math.pow(4,len(score_distribution)))
            return idx

def dscoreAnalysis(tfName, fastaFile, bedFile, pvalThreshold, outFile):

    ##############################
    ### 1. PROCESS TF MOTIF
    ##############################

    ### get JASPAR TF motif
    m = get_jaspar_motif(tfName)

    # stop if not found
    if not m:
        return None

    ppm = m.counts.normalize(pseudocounts=C_PSEUDOCOUNTS)
    pwm = ppm.log_odds(background=C_BACKGROUND)

    print "PFM:"
    print m.counts
    print "PPM:"
    print ppm
    print "PWM:"
    print pwm

    scaled_pwm = pwm2scaled_pwm(m, pwm)

    print "Scaled PWM:"
    print scaled_pwm

    score_distribution = scaled_pwm2scoredist(m, scaled_pwm)

    ### score threshold: discard motif with score smaller than this
    score_threshold = pval2score(pvalThreshold, score_distribution)

    ##############################
    ### 2. PROCESS FASTA SEQ
    ##############################

    ### LOAD FASTA SEQ
    peak_seq = collections.OrderedDict()

    for seq_item in SeqIO.parse(fastaFile,"fasta",alphabet=generic_dna):
        peak_seq[seq_item.id]=seq_item.seq
        # print seq_item.id

    print "Processing",len(peak_seq),"peaks from REF genome"

    ##############################
    ### 3. PROCESS BED
    ##############################

    with open(outFile, 'w') as output:
        with open(bedFile, 'r') as input:
            for line in input.readlines():
                line_split = line.rstrip().split("\t")
                # print line_split

                # sequence info
                seq_chr = line_split[0]
                seq_start = int(line_split[1])
                seq_end = int(line_split[2])
                skey = seq_chr+":"+str(seq_start)+"-"+str(seq_end) # 0-based
                # print skey
                seq = peak_seq[skey]
                # print seq

                # variant info
                var_chr = line_split[10]
                var_pos = int(line_split[11])-1 # 1-based pos to 0-based pos
                var_ref = line_split[13]
                var_alt = line_split[14]
                # print var_chr,var_pos,var_ref,var_alt

                # seq before variant
                seq_prefix = seq[:var_pos-seq_start]
                # seq after variant
                seq_postfix = seq[var_pos+1-seq_start:]

                left = max(var_pos+1-len(m),var_pos+1-len(seq_prefix))
                right = min(var_pos+len(m),var_pos+len(seq_postfix))
                # print left,right

                for subseq_start in range(left,right+1-len(m)):

                    ucsc_coord = seq_chr+":"+str(subseq_start+1)+"-"+str(subseq_start+len(m)) # 0-based to 1-based
                    # print ucsc_coord

                    # var pos wrt to motif
                    motif_varpos_pos = var_pos-subseq_start+1 # 1-based variant position wrt motif
                    motif_varpos_neg = len(m)-var_pos+subseq_start # 1-based variant position wrt motif
                    # print "var pos wrt TF motif (+):",motif_varpos_pos
                    # print "var pos wrt TF motif (-):",motif_varpos_neg

                    subseq_prefix = seq[subseq_start-seq_start:var_pos-seq_start]
                    subseq_var = seq[var_pos-seq_start]
                    subseq_postfix = seq[var_pos-seq_start+1:subseq_start-seq_start+len(m)]

                    if subseq_var.upper() != var_ref.upper():
                        print "WARNING! Reference sequence mismatch:",subseq_var,var_ref,var_pos
                        return None

                    subseq_ref_pos = subseq_prefix+var_ref.upper()+subseq_postfix
                    subseq_alt_pos = subseq_prefix+var_alt.upper()+subseq_postfix

                    subseq_ref_pos_print = subseq_prefix+"["+var_ref.upper()+"]"+subseq_postfix
                    subseq_alt_pos_print = subseq_prefix+"["+var_alt.upper()+"]"+subseq_postfix

                    # print subseq_ref_pos, subseq_alt_pos
                    # print subseq_ref_pos_print, subseq_alt_pos_print

                    subseq_ref_neg = subseq_ref_pos.reverse_complement()
                    subseq_alt_neg = subseq_alt_pos.reverse_complement()

                    subseq_ref_neg_print = subseq_postfix.reverse_complement()+"["+Seq(var_ref.upper(),generic_dna).reverse_complement()+"]"+subseq_prefix.reverse_complement()
                    subseq_alt_neg_print = subseq_postfix.reverse_complement()+"["+Seq(var_alt.upper(),generic_dna).reverse_complement()+"]"+subseq_prefix.reverse_complement()

                    # print subseq_ref_neg, subseq_alt_neg
                    # print subseq_ref_neg_print, subseq_alt_neg_print

                    ### calc motif score ###

                    ### FORWARD STRAND ###

                    ref_score_pos = int(seq2score(subseq_ref_pos,scaled_pwm))
                    alt_score_pos = int(seq2score(subseq_alt_pos,scaled_pwm))

                    if ref_score_pos > score_threshold or alt_score_pos > score_threshold:
                        ref_pval_pos = score2pval(ref_score_pos, score_distribution)
                        alt_pval_pos = score2pval(alt_score_pos, score_distribution)

                        dscore_pos = -10 * math.log10(ref_pval_pos/alt_pval_pos)
                        ref_rawscore_pos = seq2score(subseq_ref_pos,pwm)
                        alt_rawscore_pos = seq2score(subseq_alt_pos,pwm)
                        if abs(dscore_pos) > 0:
                            # print dscore_pos
                            output.write(seq_chr+"\t"+str(subseq_start)+"\t"+str(subseq_start+len(m))+"\t"+ucsc_coord+"_+\t"+str(dscore_pos)+"\t+\t"+str(ref_pval_pos)+"\t"+str(alt_pval_pos)+"\t"+str(subseq_ref_pos_print)+"\t"+str(subseq_alt_pos_print)+"\t"+str(ref_rawscore_pos)+"\t"+str(alt_rawscore_pos)+"\t"+str(motif_varpos_pos)+"\n")

                    ### REVERSE STRAND ###

                    ref_score_neg = int(seq2score(subseq_ref_neg,scaled_pwm))
                    alt_score_neg = int(seq2score(subseq_alt_neg,scaled_pwm))

                    if ref_score_neg > score_threshold or alt_score_neg > score_threshold:
                        ref_pval_neg = score2pval(ref_score_neg, score_distribution)
                        alt_pval_neg = score2pval(alt_score_neg, score_distribution)

                        dscore_neg = -10 * math.log10(ref_pval_neg/alt_pval_neg)
                        ref_rawscore_neg = seq2score(subseq_ref_neg,pwm)
                        alt_rawscore_neg = seq2score(subseq_alt_neg,pwm)
                        if abs(dscore_neg) > 0:
                            # print dscore_neg
                            output.write(seq_chr+"\t"+str(subseq_start)+"\t"+str(subseq_start+len(m)+1)+"\t"+ucsc_coord+"_-\t"+str(dscore_neg)+"\t-\t"+str(ref_pval_neg)+"\t"+str(alt_pval_neg)+"\t"+str(subseq_ref_neg_print)+"\t"+str(subseq_alt_neg_print)+"\t"+str(ref_rawscore_neg)+"\t"+str(alt_rawscore_neg)+"\t"+str(motif_varpos_neg)+"\n")

def bscoreAnalysis(tfName, fastaFile, pvalThreshold, outFile):

    ##############################
    ### 1. PROCESS TF MOTIF
    ##############################

    ### get JASPAR TF motif
    m = get_jaspar_motif(tfName)

    # stop if not found
    if not m:
        return None

    ppm = m.counts.normalize(pseudocounts=C_PSEUDOCOUNTS)
    pwm = ppm.log_odds(background=C_BACKGROUND)

    print "PFM:"
    print m.counts
    print "PPM:"
    print ppm
    print "PWM:"
    print pwm

    scaled_pwm = pwm2scaled_pwm(m, pwm)

    print "Scaled PWM:"
    print scaled_pwm

    score_distribution = scaled_pwm2scoredist(m, scaled_pwm)

    ### score threshold: discard motif with score smaller than this
    score_threshold = pval2score(pvalThreshold, score_distribution)

    ##############################
    ### 2. PROCESS FASTA SEQ
    ##############################

    ### LOAD FASTA SEQ
    peak_seq = collections.OrderedDict()

    for seq_item in SeqIO.parse(fastaFile,"fasta",alphabet=generic_dna):
        peak_seq[seq_item.id]=seq_item.seq
        # print seq_item.id

    print "Processing",len(peak_seq),"peaks from REF genome"

    # with open(outFile, 'w') as output:
    #     for skey in ref_seq.keys():
    #
    #         ### SLIDE WINDOW
    #         for pos in range(0,len(ref_seq[skey])-len(m)+1):
    #
    #             chr = skey.split(":")[0]
    #             pos_start = int(skey.split(":")[1].split("-")[0]) + pos + 1 ### convert 0-based to 1-based
    #             pos_end = int(skey.split(":")[1].split("-")[0]) + pos + len(m)
    #             ucsc_coord = chr+":"+str(pos_start)+"-"+str(pos_end)
    #
    #             ref_subseq_pos = ref_seq[skey][pos:pos+len(m)]
    #             ref_subseq_neg = ref_seq[skey][pos:pos+len(m)].reverse_complement()
    #
    #
    #             ### FORWARD STRAND ###
    #
    #             ref_score_pos = int(seq2score(ref_subseq_pos,scaled_pwm))
    #
    #             if ref_score_pos > score_threshold:
    #                 ref_pval_pos = score2pval(ref_score_pos, score_distribution)
    #
    #                 # dscore_pos = -10 * math.log10(ref_pval_pos/alt_pval_pos)
    #                 ref_rawscore_pos = seq2score(ref_subseq_pos,pwm)
    #
    #                 print ref_subseq_pos, ref_pval_pos
    #                 # if abs(dscore_pos) > 0:
    #                 #     # print dscore_pos
    #                 #     output.write(chr+"\t"+str(pos_start-1)+"\t"+str(pos_end)+"\t"+ucsc_coord+"_+\t"+str(dscore_pos)+"\t+\t"+str(ref_pval_pos)+"\t"+str(alt_pval_pos)+"\t"+str(ref_subseq_pos)+"\t"+str(alt_subseq_pos)+"\t"+str(ref_rawscore_pos)+"\t"+str(alt_rawscore_pos)+"\n")
    #
    #             ### REVERSE STRAND ###
    #
    #             ref_score_neg = int(seq2score(ref_subseq_neg,scaled_pwm))
    #             # alt_score_neg = int(seq2score(alt_subseq_neg,scaled_pwm))
    #
    #             if ref_score_neg > score_threshold:
    #                 ref_pval_neg = score2pval(ref_score_neg, score_distribution)
    #                 # alt_pval_neg = score2pval(alt_score_neg, score_distribution)
    #
    #                 # dscore_neg = -10 * math.log10(ref_pval_neg/alt_pval_neg)
    #                 ref_rawscore_neg = seq2score(ref_subseq_neg,pwm)
    #                 # alt_rawscore_neg = seq2score(alt_subseq_neg,pwm)
    #                 # if abs(dscore_neg) > 0:
    #                 #     # print dscore_neg
    #                 #     output.write(chr+"\t"+str(pos_start)+"\t"+str(pos_end+1)+"\t"+ucsc_coord+"_-\t"+str(dscore_neg)+"\t-\t"+str(ref_pval_neg)+"\t"+str(alt_pval_neg)+"\t"+str(ref_subseq_neg)+"\t"+str(alt_subseq_neg)+"\t"+str(ref_rawscore_neg)+"\t"+str(alt_rawscore_neg)+"\n")
    # # break