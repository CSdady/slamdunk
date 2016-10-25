#!/usr/bin/env python

# Date located in: -
from __future__ import print_function
import sys, os
import pysam
import subprocess
import collections
import csv
import ast

ReadStat = collections.namedtuple('ReadStat' , 'SequencedReads MappedReads FilteredReads')

def estimateMaxReadLength(bam):

    readfile = pysam.AlignmentFile(bam, "rb")
    
    minLength = sys.maxint
    maxLength = 0
    
    for read in readfile.head(n = 1000) :
        minLength = min(minLength, read.query_length + read.get_tag("XA"))
        maxLength = max(maxLength, read.query_length + read.get_tag("XA"))
        
    range = maxLength - minLength
    
    if (range <= 10) :
        return(maxLength + 10)
    else:
        return(-1)

#Replaces the file extension of inFile to with <newExtension> and adds a suffix
#Example replaceExtension("reads.fq", ".sam", suffix="_namg") => reads_ngm.sam
def replaceExtension(inFile, newExtension, suffix=""):    
    return os.path.splitext(inFile)[0] + suffix + newExtension

#Removes right-most extension from file name
def removeExtension(inFile):
    name = os.path.splitext(inFile)[0]
    ext = os.path.splitext(inFile)[1]
    if(ext == ".gz"):
        name = os.path.splitext(name)[0]
    return name

def getchar():
    print("Waiting for input", file=sys.stderr)
    sys.stdin.readline()

def files_exist(files):
    if (type(files) is list) :
        for f in files:
            if not os.path.exists(f):
                return False
    else:
        if not os.path.exists(files):
            return False
    return True

# remove a (list of) file(s) (if it/they exists)
def removeFile(files):
    if (type(files) is list) :
        for f in files:
            if os.path.exists(f):
                os.remove(f)
    else:
        if os.path.exists(files):
            os.remove(files)


def checkStep(inFiles, outFiles, force=False):    
    if not files_exist(inFiles):
        print(inFiles, outFiles)
        raise RuntimeError("One or more input files don't exist.")
    inFileDate = os.path.getmtime(inFiles[0])
    for x in inFiles[1:]:
        inFileDate = max(inFileDate, os.path.getmtime(x))    
    
    if len(outFiles) > 0 and files_exist(outFiles):
        outFileDate = os.path.getmtime(outFiles[0])
        for x in outFiles[1:]:
            outFileDate = min(outFileDate, os.path.getmtime(x))        
        if outFileDate > inFileDate:
            if(force == True):
                return True
            else:
                #if(os.path.getmtime(os.path.realpath(__file__)) > outFileDate):
                #    logging.info("Script was modified. Rerunning computation.")
                #else:
                #logging.critical("outFiles exist and are newer than inFiles. Skipping execution")
                #sys.exit(0)
                return False
    
    return True

def getBinary(name):
    
    projectPath = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    return os.path.join(projectPath, "contrib", name)

def getPlotter(name):
    
    projectPath = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    return os.path.join(projectPath, "plot", name + ".R")

def run(cmd, log=sys.stderr, verbose=False, dry=False):
    if(verbose or dry):
        print(cmd, file=log)
    
    if(not dry):
        #ret = os.system(cmd)
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True)
        lines_iterator = iter(p.stdout.readline, b"")
        for line in lines_iterator:
            print(line, end="", file=log) # yield line
        p.wait();
        if(p.returncode != 0):
            raise RuntimeError("Error while executing command: \"" + cmd + "\"")
        
def callR(cmd, log=sys.stderr, verbose=False, dry=False):
    
    RLIBS_VARIABLE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),"plot","Rslamdunk")
    
    if not os.path.exists(RLIBS_VARIABLE):
        os.makedirs(RLIBS_VARIABLE)
        
    os.environ['R_LIBS_SITE'] = RLIBS_VARIABLE
    
    if(verbose or dry):
        print(cmd, file=log)
    
    if(not dry):
        
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True)
        lines_iterator = iter(p.stdout.readline, b"")
        for line in lines_iterator:
            print(line, end="", file=log) # yield line
        p.wait();
        if(p.returncode != 0):
            raise RuntimeError("Error while executing command: \"" + cmd + "\"")

# def runIndexBam(inFileBam, log=sys.stderr, verbose=False, dry=False):
#     idxFile = inFileBam + ".bai"
#     if(dry or checkStep([inFileBam], [idxFile])):
#         run(" ".join([getBinary("samtools"), "index", inFileBam]), log, verbose=verbose, dry=dry)

# def runFlagstat(bam, log=sys.stderr, verbose=False, dry=False):
#     flagstat = bam + ".flagstat"
#     if(dry or checkStep([bam], [flagstat])):
#         run(" ".join([ getBinary("samtools"), "flagstat", bam, ">", flagstat]), log, verbose=verbose, dry=dry)
#     else:
#         print("Skipped flagstat for " + bam, file=log)

# def extractMappedReadCount(flagstat):
#     return int(flagstat.split("\n")[4].split(" ")[0])
# 
# def extractTotalReadCount(flagstat):
#     return int(flagstat.split("\n")[0].split(" ")[0])
# 
# def readFlagStat(bam):
#     flagStat = bam + ".flagstat"
#     if(files_exist(flagStat)):
#         with open(flagStat, 'r') as content_file:
#             content = content_file.read()
#             if content.count("\n") > 10:
#                 return ReadStat(MappedReads = extractMappedReadCount(content), TotalReads = extractTotalReadCount(content))
#     return None

def pysamIndex(outputBam):
    pysam.index(outputBam)  # @UndefinedVariable

def countReads(bam):
    bamFile = pysam.AlignmentFile(bam)
    mapped = 0
    unmapped = 0
    for read in bamFile.fetch(until_eof=True):
        if(not read.is_secondary and not read.is_supplementary):
            if(read.is_unmapped):
                unmapped += 1
            else:
                mapped += 1
    bamFile.close()
    return mapped, unmapped

def getReadCount(bam):
    bamFile = pysam.AlignmentFile(bam)
    bamFile.header
    if('RG' in bamFile.header and len(bamFile.header['RG']) > 0):
        counts = ast.literal_eval(bamFile.header['RG'][0]['DS'])
        
    else:
        raise RuntimeError("Could not get mapped/unmapped/filtered read counts from BAM file. RG is missing. Please rerun slamdunk filter.")
        
    return ReadStat(SequencedReads = counts['sequenced'], MappedReads = counts['mapped'], FilteredReads = counts['filtered'])
#     flagstat = readFlagStat(bam)
#     if(flagstat == None):
#         flagstat = countReads(bam)
#                 
#     return flagstat

def readSampleNames(sampleNames, bams):
    samples = None
    
    if(sampleNames != None and files_exist(sampleNames)):
        samples = {}
        with open(sampleNames, "r") as sampleFile:
            samplesReader = csv.reader(sampleFile, delimiter='\t')
            for row in samplesReader:
                samples[removeExtension(row[0])] = row[1]
        
    return samples

def getSampleName(fileName, samples):
    if samples == None:
        return removeExtension(fileName)
    else:
        for key in samples:
            if(key in fileName):
                return samples[key]
        
    return

def matchFile(sample, files):
    fileName = None
    for item in files:
        if(sample in item):
            if(fileName == None):
                fileName = item
            else:
                raise RuntimeError("Found more than one matching file in list.")
            
    return fileName

def complement(seq):
    complement = {'A': 'T', 'C': 'G', 'G': 'C', 'T': 'A', 'N' : 'N'} 
    bases = list(seq) 
    bases = [complement[base] for base in bases] 
    return ''.join(bases)

def shell(cmd):
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, shell=True)
    p.wait()    
    if(p.returncode != 0):
        raise RuntimeError("Error while executing command: " + cmd)
    else:
        return p.communicate()[0]

def shellerr(cmd):
    p = subprocess.Popen(cmd, stderr=subprocess.PIPE, shell=True)
    p.wait()    
    if(p.returncode != 0):
        raise RuntimeError("Error while executing command: " + cmd)
    else:
        return p.communicate()[1]  
    
