#Written by Reid McIlroy-Young for John McLevey
import os
import sys
import csv
import networkx as nx

#output file names and atributtes

writeGraphml = True
writeCSV = True

#graphml
graphOutFile = "co-CiteNetwork.graphml"

#edge list
edgeListOutFile = "co-CiteEdgeList.csv"
edgeHeader = ["Source", "Target", "Weight"]

#Node attribute list
attributeListOutFile = "co-CiteAttributeList.csv"
attributeHeader = ["Name", "Value", "Count", "Community"]

#cutoff for edges to be written weight must be >= cutoff
edgeCutoff = 2

#cutoff for nodes to be written times cited must be >= cutoff
nodeCutoff = 9

#Type of file the script looks for
inputSuffix = ".txt"

#If True removes Anonymous from citations as well as things in the next two lists
dropStuff = True

#The map and lambda is to make things uppercase add new drop conditions two the
#inner list

#This list is the string looked for in citations to remove them
droppedJournalSources = map(lambda x: x.upper(), ["SCI EXPLANATION CAUS", "ANIMAL"])

#this list is the journal name looked for in the SO field of papers to drop them
#Before there citations are analysed
droppedSOFields = map(lambda x: x.upper(), ["ANTHROZOOS","ANIMAL"])

class BadPaper(Warning):
    """
    Exception thrown by paperParser and isiParser for mis-formated papers
    """
    pass

def paperParser(paper):
    """
    paperParser reads paper until it reaches 'EF' for each field tag it adds an
    entry to the returned dict with the tag as the key and a list of the entries
    for the tag as the value, the list has each line as an entry.
    """
    tdict = {}
    currentTag = ''
    for l in paper:
        if 'ER' in l[:2]:
            return tdict
        elif '   ' in l[:3]: #the string is three spaces in row
            tdict[currentTag].append(l[3:-1])
        elif len(l) > 2 and l[2] == ' ':
            currentTag = l[:2]
            tdict[currentTag] = [l[3:-1]]
        else:
            raise BadPaper("Field tag not formed correctly: " + l)
    raise BadPaper("End of file reached before EF")

def isiParser(isifile):
    """
    isiParser reads a file, checks that the header is correct then reads each
    paper returning a list of of dicts keyed with the field tags.
    """
    f = open(isifile, 'r')
    if "VR 1.0" not in f.readline() and "VR 1.0" not in f.readline():
        raise BadPaper(isifile + " Does not have a valid header")
    notEnd = True
    plst = []
    while notEnd:
        try:
            l = f.next()
        except StopIteration as e:
            raise BadPaper("File ends before EF found")
        if not l:
            raise BadPaper("No ER found in " + isifile)
        elif l.isspace():
            continue
        elif 'EF' in l[:2]:
            notEnd = False
            continue
        else:
            try:
                if l[:2] != 'PT':
                    raise BadPaper("Paper does not start with PT tag")
                plst.append(paperParser(f))
                plst[-1][l[:2]] = l[3:-1]
            except Warning as w:
                raise BadPaper(str(w.message) + "In " + isifile)
            except Exception as e:
                 raise
    try:
        f.next()
        print "EF not at end of " + isifile
    except StopIteration as e:
        pass
    finally:
        return plst

def getFiles(suffix):
    """
    getFiles reads the current directory and returns all files ending with
    suffix. Terminates the program if none are found, no exceptions thrown.
    """
    fls = sys.argv[1:] if sys.argv[1:] else [f for f in os.listdir(".") if f.endswith(suffix)]
    if len(fls) == 0:
        #checks for any valid files
        print "No " + suffix + " Files"
        sys.exit()
    else:
        #Tells how many files were found
        print str(len(fls)) + " files found."
    return fls

def excludedSO(slst):
    if slst[0].upper() in droppedSOFields:
        return True
    else:
        return False

def excludedSource(s):
    if not dropStuff:
        return False
    elif s[0].upper() == '[ANONYMOUS]' or s[0][0] == '*':
        return True
    elif len(s) < 3:
        return False
    else:
        for droppedSource in droppedJournalSources:
            for source in s:
                if droppedSource in source.upper():
                    return True
    return False

def getIDs(clst):
    """
    Creates a dict of the ID-extra information pairs for a CR tag.
    """
    idDict = {}
    for c in clst:
        splitCit = c.split(', ')
        if len(splitCit) > 1:
            cId = splitCit[0].replace(' ',' ').replace('.','').upper() + ' ' + splitCit[1]
        else:
            cId = c.upper()
        if cId not in idDict and not excludedSource(splitCit):
            if len(splitCit) < 3:
                cExtra = ''
            elif len(splitCit[-1]) > 3 and 'DOI' in splitCit[-1][:3].upper():
                cExtra = ', '.join(splitCit[2:-1])
            else:
                cExtra = ', '.join(splitCit[2:])
            idDict[cId] = cExtra
    return idDict

def getCoauths(f, grph):
    """
    getCoauths reads f with isiParser. Then reads the CR field if there are more
    than 1 entries it assigns an ID to each citation either author date or the
    full entry if it cannot do that. Then edges are constructed between each
    node or if edges exist their weight is incremented.
    Each node also has a val field that contains the additional information that
    citation has excluding DOI number, although DOI removal is not good.
    """
    plst = isiParser(f)
    for p in plst:
        if dropStuff and 'SO' in p and excludedSO(p['SO']):
            pass
        elif 'CR' in p and len(p['CR']) > 1:
            pDict = getIDs(p['CR'])
            pIDs = pDict.keys()
            if len(pIDs) > 1:
                for i in range(len(pIDs)):
                    cId1 = pIDs[i]
                    if grph.has_node(cId1):
                        grph.node[cId1]['count'] += 1
                    else:
                        grph.add_node(cId1, val = pDict[cId1], count = 1)
                    for j in range(i + 1, len(pIDs)):
                        cId2 = pIDs[j]
                        if grph.has_node(cId2):
                            grph.node[cId2]['count'] += 1
                        else:
                            grph.add_node(cId2, val = pDict[cId2], count = 1)
                        if grph.has_edge(cId1, cId2):
                            grph.edge[cId1][cId2]['weight'] += 1
                        else:
                            grph.add_edge(cId1, cId2, weight = 1)

def csvWriteOut(Grph):
    edgeCSV = csv.writer(open(edgeListOutFile, 'w'),quotechar='"', quoting=csv.QUOTE_ALL)
    edgeCSV.writerow(edgeHeader)
    for e in Grph.edges():
        edgeCSV.writerow([e[0], e[1], Grph.edge[e[0]][e[1]]['weight']])
    attributeCSV = csv.writer(open(attributeListOutFile, 'w'),quotechar='"', quoting=csv.QUOTE_ALL)
    attributeCSV.writerow(attributeHeader)
    for n in Grph.nodes():
        attributeCSV.writerow([n, G.node[n]['val'], G.node[n]['count']])

if __name__ == '__main__':
    if writeGraphml and os.path.isfile(graphOutFile):
        #Checks if the output grpahml File already exists and terminates if so
        print graphOutFile +  " already exists\nexisting"
        sys.exit()
        #os.remove(graphOutFile)
    if writeCSV:
        #Checks if the output csv File already exists and terminates if so
        if os.path.isfile(attributeListOutFile):
            print attributeListOutFile +  " already exists\nexisting"
            sys.exit()
            #os.remove(graphOutFile)
        if os.path.isfile(edgeListOutFile):
            print edgeListOutFile +  " already exists\nexisting"
            sys.exit()
            #os.remove(graphOutFile)
    flist = getFiles(inputSuffix)
    G = nx.Graph()
    for isi in flist:
        try:
            print "Reading " + isi
            getCoauths(isi, G)
        except BadPaper as b:
            print b
        except Exception, e:
            #If any exceptions are raised cleans up and prints them
            print 'Exception:'
            print e
            print "Deleting " + graphOutFile
            if os.path.isfile(graphOutFile):
                os.remove(graphOutFile)
            raise
    print "Trimming nodes"
    for n in G.nodes():
            if G.node[n]['count'] <= nodeCutoff:
                  G.remove_node(n)
    print "Trimming edges"
    for ed in G.edges():
            if G[ed[0]][ed[1]]['weight'] <= edgeCutoff:
                  G.remove_edge(ed[0],ed[1])
    if writeGraphml:
        print "Writing graphml " + graphOutFile
        nx.write_graphml(G, graphOutFile)
    if writeCSV:
        print "Writing CSVs " + edgeListOutFile + " and " + attributeListOutFile
        csvWriteOut(G)
    print "Done"
