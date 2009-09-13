from Gui import showGui

from optparse import OptionParser
import os
import wx

def printStats(statsData):
    print 'Functions which used up most of the CPU time, including time spend in subfunctions:'
    print
    statsData.sort_stats('cumulative').print_stats(25)
    
    print 'Functions which used up most of the CPU time, excluding time spend in subfunctions:'
    print
    statsData.sort_stats('time').print_stats(25)
    
    print 'Functions which were called most:'
    print
    statsData.sort_stats('calls').print_stats(25)




def main():
    #parse commandline arguments
    parser = OptionParser()
    parser.set_usage("%prog [options]")
    parser.add_option("-p", "--profile", action="store_true", dest="profile", default=False,
                      help="enables profiling of the entire program, prints statistics after program exit")    

    (options, args) = parser.parse_args()
    
    if len(args) != 0:
        #invalid options
        parser.print_help()
    
    else:
        #valid options
        currentPath = os.getcwdu()
        if not options.profile:
            #no profiling, just show the gui
            showGui(currentPath)
            
        else:
            #profiling
            import cProfile
            import pstats
            
            statsFile = os.path.join(currentPath,'profilingStats')
            
            #show gui, profile until gui exits
            cProfile.runctx('showGui(currentPath)', globals(), {'currentPath':currentPath}, statsFile)
            
            #load profiling data
            statsData = pstats.Stats(statsFile)
            
            #print profiling stats
            printStats(statsData)
            #statsData.strip_dirs() #strip leading path info, shortens output
            #printStats(statsData)

if __name__=='__main__':
    main()