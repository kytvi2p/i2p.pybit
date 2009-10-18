"""
Copyright 2009  Blub

PyBit.py, contains a class and a few functions which, as the name already implies, start PyBit 
(after parsing the commandline and setting up a profiler if needed)
This file is part of PyBit.

PyBit is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published
by the Free Software Foundation, version 2 of the License.

PyBit is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with PyBit.  If not, see <http://www.gnu.org/licenses/>.
"""

VERSION = '0.2.4'


##builtin
from optparse import OptionParser
import logging
import os
import wx

##own
from Bittorrent.MultiBt import MultiBt, MultiBtException
from Config import Config
from Gui import showGui
from LogController import LogController
from ObjectPersister import ThreadedObjectPersister
from Utilities import logTraceback


class PyBit:
    def __init__(self, progPath, version):
        self.progPath = progPath
        self.version = version
        self.log = logging.getLogger('PyBit')
        
        
    def _start(self):
        #create log controller
        self.logController = LogController((('consoleLog', 'consoleLog', {'logLevel':'critical',
                                                                          'logFormat':'%(asctime)s %(levelname)-8s %(name)-22s - %(message)s'}),
                                            ('fileLog'   , 'fileLog'   , {'filename':os.path.join(self.progPath, u'Logs', u'log'),
                                                                          'logLevel':'info',
                                                                          'logFormat':'%(asctime)s %(levelname)-8s %(name)-22s - %(message)s',
                                                                          'fileMaxBytes':10485760,
                                                                          'fileMaxRotatedCount':4})))
                            
        #create config, set defaults
        configDefaults = {'choker':{'chokeInterval':(60, 'int'),
                                    'randomSlotRatio':(0.1, 'float'),
                                    'maxSlots':(10, 'int'),
                                    'slotLimitScope':('global', 'str')},
                          'http':{'torrentFetchRetryInterval':(60, 'int'),
                                  'torrentFetchTransferTimeout':(120, 'int'),
                                  'torrentFetchRequestTimeout':(600, 'int'),
                                  'torrentFetchMaxHeaderSize':(4096, 'int'),
                                  'torrentFetchMaxDataSize':(1048576, 'int'),
                                  'trackerRequestTransferTimeout':(120, 'int'),
                                  'trackerRequestTimeout':(300, 'int'),
                                  'trackerRequestMaxHeaderSize':(4096, 'int'),
                                  'trackerRequestMaxDataSize':(1048576, 'int')},
                          'i2p':{'samIp':('127.0.0.1', 'ip'),
                                 'samPort':(7656, 'port'),
                                 'samDisplayName':('PyBit', 'str'),
                                 'samSessionName':('PyBit', 'str'),
                                 'samZeroHopsIn':(False, 'bool'),
                                 'samZeroHopsOut':(False, 'bool'),
                                 'samNumOfTunnelsIn':(3, 'int'),
                                 'samNumOfTunnelsOut':(3, 'int'),
                                 'samNumOfBackupTunnelsIn':(0, 'int'),
                                 'samNumOfBackupTunnelsOut':(0, 'int'),
                                 'samTunnelLengthIn':(2, 'int'),
                                 'samTunnelLengthOut':(2, 'int'),
                                 'samTunnelLengthVarianceIn':(0, 'int'),
                                 'samTunnelLengthVarianceOut':(0, 'int')},
                          'logging':{'consoleLoglevel':('critical', 'str'),
                                     'fileLoglevel':('info', 'str')},
                          'network':{'downSpeedLimit':(102400, 'int'),
                                     'upSpeedLimit':(25600, 'int')},
                          'paths':{'torrentFolder':(self.progPath, 'unicode'),
                                   'downloadFolder':(self.progPath, 'unicode')},
                          'requester':{'strictAvailabilityPrio':(True, 'bool')},
                          'storage':{'persistPieceStatus':(True, 'bool'),
                                     'skipFileCheck':(False, 'bool')},
                          'tracker':{'scrapeWhileStopped':(False, 'bool'),
                                     'scrapeTrackers':('active', 'str')}}
                                    
        self.config = Config(os.path.join(self.progPath, u'config.conf'), configDefaults=configDefaults)
        
        #set real log options and add callbacks
        self.logController.changeHandlerLoglevel('consoleLog', self.config.get('logging','consoleLoglevel'))
        self.logController.changeHandlerLoglevel('fileLog', self.config.get('logging','fileLoglevel'))
        self.config.addCallback((('logging', 'consoleLoglevel'),), self.logController.changeHandlerLoglevel, funcArgs=['consoleLog'], valueArgPlace=1)
        self.config.addCallback((('logging', 'fileLoglevel'),), self.logController.changeHandlerLoglevel, funcArgs=['fileLog'], valueArgPlace=1)
        
        #create persister
        self.log.info("Creating object persister instance")
        self.persister = ThreadedObjectPersister(os.path.join(self.progPath, u'state.db'), log='ObjectPersister')
        self.persister.start()
        
        #creat torrent handler
        self.torrentHandler = MultiBt(self.config, self.persister, self.progPath, self.version)
        
        
    def _stop(self):
        try:
            self.log.info('Stopping torrent handler')
            self.torrentHandler.stop()
            self.log.debug('Stopping persister')
            self.persister.stop()
            self.log.debug('Cleanup of log related things')
            self.logController.shutdown()
        except:
            self.log.error("Failure while shutting down:\n%s", logTraceback())
        
        
    def run(self):
        self._start()
        showGui(self.progPath, self.config, self.torrentHandler, self.persister, self.version)
        self._stop()
    
    
    

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
        prog = PyBit(currentPath, VERSION)
        
        if not options.profile:
            #no profiling, just show the gui
            prog.run()
            
        else:
            #profiling
            statsFile = os.path.join(currentPath,'profilingStats')
            
            if options.profiler == 'cProfile':
                import cProfile
                import pstats
                
                #show gui, profile until gui exits
                cProfile.runctx('prog.run()', globals(), locals(), statsFile)
                
                #load profiling data
                statsData = pstats.Stats(statsFile)
                
                #print profiling stats
                printStats(statsData)
                
            elif options.profiler == 'hotshot':
                import hotshot, hotshot.stats
                prof = hotshot.Profile(statsFile)
                prof.runcall(prog.run)
                prof.close()
                statsData = hotshot.stats.load(statsFile)
                
                #print profiling stats
                printStats(statsData)
                
            else:
                from Profiler import Profiler
                prof = Profiler()
                prof.start()
                prog.run()
                prof.stop()
                prof.printStats()
            
            #statsData.strip_dirs() #strip leading path info, shortens output
            #printStats(statsData)
            

if __name__=='__main__':
    main()