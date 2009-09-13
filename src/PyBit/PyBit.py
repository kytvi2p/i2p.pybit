from Gui import showGui

from optparse import OptionParser
import os
import wx

def printStats(statsData):
    print 'Functions which used up most of the CPU time, including time spend in subfunctions:'
    print
    statsData.sort_stats('cumulative').print_stats(50)
    
    print 'Functions which used up most of the CPU time, excluding time spend in subfunctions:'
    print
    statsData.sort_stats('time').print_stats(50)
    
    print 'Functions which were called most:'
    print
    statsData.sort_stats('calls').print_stats(50)




def main():
    #parse commandline arguments
    parser = OptionParser()
    parser.set_usage("%prog [options]")
    parser.add_option("-p", "--profile", action="store_true", dest="profile", default=False,
                      help="enables profiling of the entire program, prints statistics after program exit")
    parser.add_option("-m", "--method", dest="profiler", default="cProfile",
                      help='determines which profiler ("cProfile" or "hotshot") is used')

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
            statsFile = os.path.join(currentPath,'profilingStats')
            
            if options.profiler == 'cProfile':
                import cProfile
                import pstats
                
                #show gui, profile until gui exits
                cProfile.runctx('showGui(currentPath)', globals(), {'currentPath':currentPath}, statsFile)
                
                #load profiling data
                statsData = pstats.Stats(statsFile)
                
                #print profiling stats
                printStats(statsData)
                
            elif options.profiler == 'hotshot':
                import hotshot, hotshot.stats
                prof = hotshot.Profile(statsFile)
                prof.runcall(showGui, currentPath)
                prof.close()
                statsData = hotshot.stats.load(statsFile)
                
                #print profiling stats
                printStats(statsData)
                
            else:
                from Profiler import Profiler
                prof = Profiler()
                prof.start()
                showGui(currentPath)
                prof.stop()
                prof.printStats()
            
            #statsData.strip_dirs() #strip leading path info, shortens output
            #printStats(statsData)

if __name__=='__main__':
    main()