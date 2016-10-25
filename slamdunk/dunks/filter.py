#!/usr/bin/env python

# Date located in: -
from __future__ import print_function
import pysam, random, os
from intervaltree import IntervalTree


from slamdunk.utils.BedReader import BedIterator
from slamdunk.utils.misc import checkStep, run, removeFile, getBinary, countReads, pysamIndex

# def Filter_old(inputBAM, outputBAM, log, MQ=2, printOnly=False, verbose=True, force=True):
#     if(printOnly or checkStep([inputBAM], [outputBAM], force)):
#         run(" ".join([ getBinary("samtools"), "view -q", str(MQ), "-b", inputBAM, ">", outputBAM]), log, verbose=verbose, dry=printOnly)
#     else:
#         print("Skipped filtering for " + inputBAM, file=log)
# 
#     runIndexBam(outputBAM, log, verbose=verbose, dry=printOnly)
#     runFlagstat(outputBAM, log, verbose=verbose, dry=printOnly)
    
def bamSort(outputBAM, log, newHeader, verbose):
    
    tmp = outputBAM + "_tmp"
    if(newHeader != None):
        pyOutputBAM = pysam.AlignmentFile(outputBAM, "rb")    
        pyTmp = pysam.AlignmentFile(tmp, "wb", header=newHeader)
        for read in pyOutputBAM:
            pyTmp.write(read)
        pyOutputBAM.close()
        pyTmp.close()
    else:
        os.rename(outputBAM, tmp)
                              
    #run(" ".join(["samtools", "sort", "-@", str(threads) , tmp, replaceExtension(outFile, "")]), log, verbose=verbose, dry=dry)
    run(" ".join([getBinary("samtools"), "sort", "-o", outputBAM, tmp]), log, verbose=verbose, dry=False)
    #pysam.sort(tmp, outputBAM)  # @UndefinedVariable
    removeFile(tmp)
    
def bedToIntervallTree(bed):
    utrs = {}
        
    for utr in BedIterator(bed):

        if (not utrs.has_key(utr.chromosome)) :
            utrs[utr.chromosome] = IntervalTree()
        
        utrs[utr.chromosome][utr.start:(utr.stop + 1)] = utr.name
        
    return utrs
    
def dumpBufferToBam (buffer, multimapList, outbam, infile):
    # Randomly write hit from read
    read = random.choice(buffer.values()).pop()
#     printer = read.query_name + "\t" + infile.getrname(read.reference_id) + "\t" + str(read.reference_start) + "\t" + str(read.reference_end) + "\tPRINT\tTrue"
    read.set_tag("RD", multimapList.rstrip(" "), "Z")
    outbam.write(read)
    
#     return printer
#     for key in buffer.keys():
#         for read in buffer[key]:
#             outbam.write(read)
            
def multimapUTRRetainment (infile, outfile, bed, minIdentity, NM):
    
    mappedReads = 0
    unmappedReads = 0
    filteredReads = 0    
    
    utrIntervallTreeDict = bedToIntervallTree(bed)
    
#     debugLog = os.path.join("multimapdebug.log")
#     
#     fo = open(debugLog, "w")
    
    # Buffers for multimappers
    multimapBuffer = {}
    prevRead = ""
    # If read maps to another than previously recorded UTR -> do not dump reads to file
    dumpBuffer = True
    # This string tracks all multiple alignments
    multimapList = ""
#     logList = []
    
    for read in infile:
        if(not read.is_secondary and not read.is_supplementary):
            if(read.is_unmapped):
                unmappedReads += 1
            else:
                mappedReads += 1
                
        # First pass general filters
        if(read.is_unmapped):
            continue
        if(float(read.get_tag("XI")) < minIdentity):
            continue
        if(NM > -1 and int(read.get_tag("NM")) > NM):
            continue
        if (read.mapping_quality == 0) :
            # Previous read was also multimapper
            if (read.query_name != prevRead and prevRead != "") :
                
                #if (dumpBuffer and (len(multimapBuffer) > 1 or len(multimapBuffer["nonUTR"]) > 0)) :
                if (dumpBuffer and len(multimapBuffer) > 0) :
                    dumpBufferToBam(multimapBuffer, multimapList, outfile, infile)
                    filteredReads += 1
#                     ret = dumpBufferToBam(multimapBuffer, outfile, infile)
#                     print(ret,file = fo)
                    multimapBuffer = {}
                    #multimapBuffer["nonUTR"] = []
                       
#                 for entry in logList:
#                     print(prevRead + "\t" + entry + "\t" + str(dumpBuffer), file = fo)
#                 logList = []
                     
                dumpBuffer = True
                multimapList = ""
                
            # Query Intervall tree for given chromosome for UTs
            chr = infile.getrname(read.reference_id)
            start = read.reference_start
            end = read.reference_end
            
            if (utrIntervallTreeDict.has_key(chr)) :
                query = utrIntervallTreeDict[chr][start:end]
            else :
                query = set()
            
            if len(query) > 0:
                # First UTR hit is recorded without checks
                if (len(multimapBuffer) == 0) :
                    for result in query :
                        if (not multimapBuffer.has_key(result.data)) :
                            multimapBuffer[result.data] = []
                        multimapBuffer[result.data].append(read)
                # Second UTR hit looks at previous UTR hits -> no dump if hit on different UTR
                else :
                    for result in query :
                        if (not multimapBuffer.has_key(result.data)) :
                            multimapBuffer[result.data] = []
                            multimapBuffer[result.data].append(read)
                            dumpBuffer = False
                        else :
                            multimapBuffer[result.data].append(read)
#             else :
#                 # If no overlap -> nonUTR
#                 multimapBuffer["nonUTR"].append(read)
#                 for result in query :
#                     logList.append(chr + "\t" + str(start) + "\t" + str(end) + "\t" + result.data)
#             else :
#                 logList.append(chr + "\t" + str(start) + "\t" + str(end) + "\t" + "OFF")
            
            multimapList = multimapList + chr + ":" + str(start) + "-" + str(end) + " "
            
            prevRead = read.query_name
        else :
            # Dump any multimappers before a unique mapper
            #if (len(multimapBuffer) > 1 or len(multimapBuffer["nonUTR"]) > 0) :
            if (len(multimapBuffer) > 0) :
                if (dumpBuffer) :
                    dumpBufferToBam(multimapBuffer, multimapList, outfile, infile)
                    filteredReads += 1
#                     ret = dumpBufferToBam(multimapBuffer, outfile, infile)
#                     print(ret,file = fo)
                multimapBuffer = {}
#                 for entry in logList:
#                     print(prevRead + "\t" + entry + "\t" + str(dumpBuffer), file = fo)
#                 logList = []
                #multimapBuffer["nonUTR"] = []
                dumpBuffer = True
                multimapList = ""
                
            # Record all unique mappers
            prevRead = read.query_name
            outfile.write(read)
            filteredReads += 1
            
    # Dump last portion if it was multimapper
    #if (dumpBuffer and (len(multimapBuffer) > 1 or len(multimapBuffer["nonUTR"]) > 0)) :
    if (dumpBuffer and len(multimapBuffer) > 0) :
        dumpBufferToBam(multimapBuffer, multimapList, outfile, infile)
        filteredReads += 1
        
#     fo.close()
    return mappedReads, unmappedReads, filteredReads
        
        
def Filter(inputBAM, outputBAM, log, bed, MQ=2, minIdentity=0.8, NM=-1, printOnly=False, verbose=True, force=False):
    if(printOnly or checkStep([inputBAM], [outputBAM], force)):
        
        mappedReads = 0
        unmappedReads = 0
        filteredReads = 0
        
        infile = pysam.AlignmentFile(inputBAM, "rb")    
        outfile = pysam.AlignmentFile(outputBAM, "wb", template=infile)
        
        # Default filtering without bed
        if (bed == None) :
            
            print("No bed-file supplied. Running default filtering on " + inputBAM + ".",file=log)
            
            for read in infile:
                
                if(not read.is_secondary and not read.is_supplementary):
                    if(read.is_unmapped):
                        unmappedReads += 1
                    else:
                        mappedReads += 1
                
                if(read.is_unmapped):
                    continue
                if(read.mapping_quality < MQ):
                    continue
                if(float(read.get_tag("XI")) < minIdentity):
                    continue
                if(NM > -1 and int(read.get_tag("NM")) > NM):
                    continue
                
                if(not read.is_secondary and not read.is_supplementary):
                    filteredReads += 1
                outfile.write(read)
        else :
            # Multimap retention strategy filtering when bed is supplied
            
            print("Bed-file supplied. Running multimap retention filtering strategy on " + inputBAM + ".",file=log)
            mappedReads, unmappedReads, filteredReads = multimapUTRRetainment (infile, outfile, bed, minIdentity, NM)
        
        # Add number of sequenced and number of mapped reads to the read group description
        # Used for creating summary file
        inFileBamHeader = outfile.header
        if('RG' in inFileBamHeader and len(inFileBamHeader['RG']) > 0):
            inFileBamHeader['RG'][0]['DS'] = "{'sequenced':" + str(mappedReads + unmappedReads) + "," + "'mapped':" + str(mappedReads) + "," + "'filtered':" + str(filteredReads) + "}"        
        
        infile.close()
        outfile.close()
        
        # Sort afterwards
        bamSort(outputBAM, log, inFileBamHeader, verbose)
        
        pysamIndex(outputBAM)
        #pysamFlagstat(outputBAM)
        #runFlagstat(outputBAM, log, verbose=verbose, dry=printOnly)
    
    else:
        print("Skipped filtering for " + inputBAM, file=log)

    