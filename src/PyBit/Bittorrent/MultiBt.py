"""
Copyright 2009  Blub

MultiBt, a class for managing multiple torrent jobs (Bt classes) at once.
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

##buildin
import logging
import os
import threading

##own classes
from Bt import Bt
from Conversion import shortIntToBinary
from ConnectionBuilder import ConnectionBuilder
from ConnectionHandler import ConnectionHandler
from ConnectionListener import ConnectionListener
from ConnectionPool import ConnectionPool
from EventScheduler import EventScheduler
from HttpRequester import HttpRequester
from Limiter import RefillingQuotaLimiter
from Measure import Measure
from OwnAddressWatcher import OwnAddressWatcher
from Torrent import Torrent
from Utilities import generateRandomBinary, encodeStrForPrinting, logTraceback
from PySamLib.SamSocketManager import SamSocketManager

#DEBUG
#import gc

VERSION = '0.0.1'


class MultiBtException(Exception):
    pass


class MultiBt:
    def __init__(self, config, persister, progPath):
        self.config = config
        self.persister = persister
        self.progPath = progPath
        
        #DEBUG
        #gc.set_debug(gc.DEBUG_UNCOLLECTABLE)
        #gc.set_debug(gc.DEBUG_LEAK)
        #gc.set_debug(gc.DEBUG_COLLECTABLE | gc.DEBUG_UNCOLLECTABLE | gc.DEBUG_INSTANCES | gc.DEBUG_OBJECTS)
        
        #log
        self.log = logging.getLogger('MultiBt')
        
        #set config defaults
        configDefaults = {'connections':{'downSpeed':(102400, 'int'),
                                         'upSpeed':(10240, 'int')},
                          'i2p':{'samIp':('127.0.0.1', 'ip'),
                                 'samPort':(7656, 'port'),
                                 'samSessionName':('PyBit', 'str'),
                                 'samZeroHopsIn':(False, 'bool'),
                                 'samZeroHopsOut':(False, 'bool'),
                                 'samNumOfTunnelsIn':(2, 'int'),
                                 'samNumOfTunnelsOut':(2, 'int'),
                                 'samNumOfBackupTunnelsIn':(0, 'int'),
                                 'samNumOfBackupTunnelsOut':(0, 'int'),
                                 'samTunnelLengthIn':(2, 'int'),
                                 'samTunnelLengthOut':(2, 'int'),
                                 'samTunnelLengthVarianceIn':(1, 'int'),
                                 'samTunnelLengthVarianceOut':(1, 'int')}}
        self.config.addDefaults(configDefaults)
        
        #generate peerid
        versionDigits = VERSION.split('.')
        self.peerId = '-PB' + shortIntToBinary(versionDigits[0]) + shortIntToBinary(versionDigits[1]) +\
                      shortIntToBinary(versionDigits[2]) + generateRandomBinary(14)
                    
        #create samSocketManager
        samOptions = {'inbound.nickname':self.config.get('i2p','samSessionName'),
                      'inbound.quantity':self.config.get('i2p','samNumOfTunnelsIn'),
                      'inbound.backupQuantity':self.config.get('i2p','samNumOfBackupTunnelsIn'),
                      'inbound.length':self.config.get('i2p','samTunnelLengthIn'),
                      'inbound.lengthVariance':self.config.get('i2p','samTunnelLengthVarianceIn'),
                      'inbound.allowZeroHop':self.config.get('i2p','samZeroHopsIn'),
                      'outbound.quantity':self.config.get('i2p','samNumOfTunnelsOut'),
                      'outbound.backupQuantity':self.config.get('i2p','samNumOfBackupTunnelsOut'),
                      'outbound.length':self.config.get('i2p','samTunnelLengthOut'),
                      'outbound.lengthVariance':self.config.get('i2p','samTunnelLengthVarianceOut'),
                      'outbound.allowZeroHop':self.config.get('i2p','samZeroHopsOut')}
                    
        self.samSockManager = SamSocketManager(log='SamSocketManager', asmLog='AsyncSocketManager')
        self.destNum = self.samSockManager.addDestination(self.config.get('i2p','samIp'),
                                                          self.config.getInt('i2p','samPort'),
                                                          self.config.get('i2p','samSessionName'),
                                                          'tcp', 'both', samOptions)
        
        #create event scheduler
        self.eventSched = EventScheduler()
        
        #create traffic related classes
        self.inLimiter = RefillingQuotaLimiter(self.eventSched, self.config.getInt('connections','downSpeed'))
        self.outLimiter = RefillingQuotaLimiter(self.eventSched, self.config.getInt('connections','upSpeed'))
        self.inRate = Measure(self.eventSched, 60)
        self.outRate = Measure(self.eventSched, 60)
        
        #create connection related classes
        self.connPool = ConnectionPool()
        self.connHandler = ConnectionHandler(self.config, self.connPool, self.samSockManager.select, self.eventSched,\
                                             self.inLimiter, self.outLimiter, self.peerId)
        self.connListener = ConnectionListener(self.connHandler, self.connPool, self.destNum, self.samSockManager, self.peerId)
        self.connBuilder = ConnectionBuilder(self.eventSched, self.connHandler, self.connPool, self.destNum, self.samSockManager, self.peerId)
        
        #create own address watcher class
        self.ownAddrWatcher = OwnAddressWatcher(self.destNum, self.samSockManager)
        
        #create http requester class
        self.httpRequester = HttpRequester(self.eventSched, self.destNum, self.samSockManager, self.ownAddrWatcher.getOwnAddr)
        
        #queue related structures
        self.torrentId = 1
        self.torrentQueue = []
        self.torrents = {}
        self._loadTorrentQueue()
        
        #lock
        self.lock = threading.Lock()
        
 
    ##internal functions - queue
    
    def _getQueueIndex(self, torrentId):
        index = None
        place = 0
        while index is None:
            if self.torrentQueue[place]['id'] == torrentId:
                index = place
            else:
                place += 1
        return index
        
        
    def _loadTorrentQueue(self):
        #load old queue from db and restore bt jobs
        oldQueue, version = self.persister.get('MultiBt-torrentQueue', ([], VERSION))
        while len(oldQueue) > 0:
            #not empty, process next queue element
            queueElement = oldQueue[0]
            del oldQueue[0]
            
            #increase id if needed
            if self.torrentId <= queueElement['id']:
                self.torrentId = queueElement['id'] + 1
            
            #add torrent to queue
            success, failureMsg = self._addTorrent(queueElement['id'], queueElement['dataPath'])
#            if success:
#                #torrent is added, now start it, if it was running before
#                if queueElement['state'] == 'running':
#                    self._startTorrent(queueElement['id'])
    
    
    def _storeTorrentQueue(self):
        self.persister.store('MultiBt-torrentQueue', (self.torrentQueue, VERSION))
                    
                    
    def _moveUp(self, torrentIndex):
        if not torrentIndex == 0:
            queueElement = self.torrentQueue[torrentIndex]
            del self.torrentQueue[torrentIndex]
            self.torrentQueue.insert(torrentIndex-1, queueElement)
            self._storeTorrentQueue()
            
            
    def _moveDown(self, torrentIndex):
        if not torrentIndex == len(self.torrentQueue)-1:
            queueElement = self.torrentQueue[torrentIndex]
            del self.torrentQueue[torrentIndex]
            self.torrentQueue.insert(torrentIndex+1, queueElement)
            self._storeTorrentQueue()
    
    
    ##internal functions - torrent
    
    def _getTorrentFilePath(self, torrentId):
        return os.path.join(self.progPath, 'Torrents', str(torrentId)+'.torrent')
    

    def _addTorrent(self, torrentId, torrentDataPath):
        success = True
        failureMsg = None
        
        #try to load torrent data from the usual place
        torrentFilePath = self._getTorrentFilePath(torrentId)
        self.log.debug('Torrent %i: trying to read torrent data from "%s"', torrentId, torrentFilePath)
        try:
            fl = open(torrentFilePath, 'rb')
            torrentFileData = fl.read()
            fl.close()
        except:
            success = False
            failureMsg = 'Could not read torrent file from "%s"' % encodeStrForPrinting(torrentFilePath)
    
        if success:
            #successfully read the torrent data
            self.log.debug('Torrent %i: trying to parse read torrent data', torrentId)
            torrent = Torrent()
            try:
                torrent.load(torrentFileData)
            except:
                success = False
                failureMsg = 'Failed to parse torrent file "%s"!\nTraceback: %s' % (encodeStrForPrinting(torrentFilePath), logTraceback())
                
            if success:
                #valid torrent data
                self.log.debug('Torrent %i: creating bt class', torrentId)
                btObj = Bt(self.config, self.eventSched, self.httpRequester, self.ownAddrWatcher.getOwnAddr, self.peerId, self.inRate, self.outRate,
                           self.connPool, self.connBuilder, self.connListener, self.connHandler, torrent, 'Bt'+str(torrentId), torrentDataPath)
                
                #add to queue
                self.log.debug('Torrent %i: adding to queue', torrentId)
                self.torrents[torrentId] = btObj
                self.torrentQueue.append({'id':torrentId,
                                          'state':'stopped',
                                          'dataPath':torrentDataPath})
                
                #save updated queue to disk
                self.log.debug('Torrent %i: saving queue to disk', torrentId)
                self._storeTorrentQueue()
                
        if not success:
            self.log.info("Failed to add torrent, reason: %s", failureMsg)
                
        return success, failureMsg
    
    
    def _startTorrent(self, torrentId):
        #adapt queue
        queueIndex = self._getQueueIndex(torrentId)
        self.torrentQueue[queueIndex]['state'] = 'running'
        self._storeTorrentQueue()
        
        #really start torrent
        self.torrents[torrentId].start()
        
        
    def _stopTorrent(self, torrentId):
        #adapt queue
        queueIndex = self._getQueueIndex(torrentId)
        self.torrentQueue[queueIndex]['state'] = 'stopped'
        self._storeTorrentQueue()
        
        #really stop torrent
        self.torrents[torrentId].pause()
        
        
    def _removeTorrent(self, torrentId):
        #remove from queue
        queueIndex = self._getQueueIndex(torrentId)
        del self.torrentQueue[queueIndex]
        self._storeTorrentQueue()
        
        #stop torrent then delete entry
        self.torrents[torrentId].stop()
        del self.torrents[torrentId]
        
        #remove internal torrent file
        try:
            os.remove(self._getTorrentFilePath(torrentId))
        except:
            pass
        
        
    def _getTorrentStats(self, torrentId):
        stats = {}
        queueIndex = self._getQueueIndex(torrentId)
        stats['id'] = torrentId
        stats['pos'] = queueIndex + 1
        stats['state'] = self.torrentQueue[queueIndex]['state']
        return stats
        
        
    ##external functions - torrents
        
    
    def addTorrent(self, torrentFileData, torrentDataPath):
        self.lock.acquire()
        
        #get id
        torrentId = self.torrentId
        self.torrentId += 1
        
        #store torrent file in torrent directory
        torrentFilePath = self._getTorrentFilePath(torrentId)
        try:
            fl = open(torrentFilePath, 'wb')
            fl.write(torrentFileData)
            fl.close()
        except:
            self.lock.release()
            raise MultiBtException('Failed to save torrent data to "%s"' % encodeStrForPrinting(torrentFilePath))
        
        #add to queue
        success, failureMsg = self._addTorrent(torrentId, torrentDataPath)
        self.lock.release()
        if not success:
            raise MultiBtException('Failed to add torrent: "%s"' % failureMsg)
        else:
            return torrentId
        
        
    def startTorrent(self, torrentId):
        self.lock.acquire()
        if torrentId in self.torrents:
            self._startTorrent(torrentId)
        self.lock.release()
    
    
    def stopTorrent(self, torrentId):
        self.lock.acquire()
        if torrentId in self.torrents:
            self._stopTorrent(torrentId)
        self.lock.release()
    
    
    def removeTorrent(self, torrentId):
        self.lock.acquire()
        if torrentId in self.torrents:
            self._removeTorrent(torrentId)
        self.lock.release()
        
        
    def isTorrentStarted(self, torrentId):
        self.lock.acquire()
        started = False
        if torrentId in self.torrents:
            torrentIndex = self._getQueueIndex(torrentId)
            if self.torrentQueue[torrentIndex]['state'] == 'running':
                started = True
        self.lock.release()
        return started
        
        
    ##external functions - queue
    
    def moveUp(self, torrentId):
        self.lock.acquire()
        if torrentId in self.torrents:
            torrentIndex = self._getQueueIndex(torrentId)
            self._moveUp(torrentIndex)
        self.lock.release()
    
    
    def moveDown(self, torrentId):
        self.lock.acquire()
        if torrentId in self.torrents:
            torrentIndex = self._getQueueIndex(torrentId)
            self._moveDown(torrentIndex)
        self.lock.release()
        
    
    ##external functions - stats
    
    def getStats(self, wantedStats={}, wantedTorrentStats={}):
        self.lock.acquire()
        stats = {}
        
        #transfer stats
        if wantedStats.get('transfer', False):
            stats['inPayloadBytes'] = self.inRate.getTotalTransferedPayloadBytes()
            stats['outPayloadBytes'] = self.outRate.getTotalTransferedPayloadBytes()
            stats['inRawSpeed'] = self.inRate.getCurrentRate()
            stats['outRawSpeed'] = self.outRate.getCurrentRate()
        
        #bt stats
        btStats = wantedStats.get('bt')
        if btStats is not None:
            #wants some bt stats
            if type(btStats) == int:
                #single bt stats
                stats['bt'] = self.torrents[btStats].getStats(wantedTorrentStats)
                if wantedTorrentStats.get('queue', False):
                    #queue stats
                    stats['bt'].update(self._getTorrentStats(btStats))
                
            else:
                #wants all
                statList = []
                for torrentId in self.torrents.iterkeys():
                    #get stats for each torrent
                    statItem = self.torrents[torrentId].getStats(wantedTorrentStats)
                    if wantedTorrentStats.get('queue', False):
                        #queue stats
                        statItem.update(self._getTorrentStats(torrentId))
                        
                    statList.append(statItem)
                stats['bt'] = statList
                
        self.lock.release()
        return stats
        
        
    ##external functions - other
    
    def stop(self):
        self.lock.acquire()
        self.log.info("Stopping")
        
        #stop all bt jobs without modifying the queue
        self.log.info("Stopping all bt jobs")
        for btJob in self.torrents.itervalues():
            btJob.stop()
        
        #stop http requester
        self.log.info("Stopping http requester")
        self.httpRequester.stop()
        
        #stop all connection related classes
        self.log.info("Stopping all connection related classes")
        self.connPool.stop()
        self.connHandler.stop()
        self.connListener.stop()
        self.connBuilder.stop()
        
        #stop traffic related classes
        self.log.info("Stopping limiter and measurer")
        self.inLimiter.stop()
        self.outLimiter.stop()
        self.inRate.stop()
        self.outRate.stop()
        
        #stop event scheduler
        self.log.info("Stopping event scheduler")
        self.eventSched.stop()
        
        #remove destination
        self.log.info("Stopping sam socket manager")
        self.samSockManager.removeDestination(self.destNum)
        self.samSockManager.shutdown()
        
        self.lock.release()
