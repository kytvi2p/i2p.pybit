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
from __future__ import with_statement
import logging
import os
import re
import threading

##own classes
from Bt import Bt
from Conversion import shortIntToBinary
from ConnectionBuilder import ConnectionBuilder
from ConnectionHandler import ConnectionHandler
from ConnectionListener import ConnectionListener
from PeerPool import PeerPool
from EventScheduler import EventScheduler
from HttpRequester import HttpRequester
from Limiter import RefillingQuotaLimiter
from Measure import Measure
from OwnAddressWatcher import OwnAddressWatcher
from Torrent import Torrent, TorrentException
from Utilities import generateRandomBinary, encodeStrForPrinting, logTraceback
from PySamLib.I2PSocketManager import I2PSocketManager

#DEBUG
#import gc

VERSION = '0.1.0'


class MultiBtException(Exception):
    def __init__(self, reason, *args):
        self.reason = reason % args
        Exception.__init__(self, self.reason)


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
        
        #generate peerid
        versionDigits = VERSION.split('.')
        self.peerId = '-PB' + shortIntToBinary(versionDigits[0]) + shortIntToBinary(versionDigits[1]) +\
                      shortIntToBinary(versionDigits[2]) + generateRandomBinary(14)
                    
        #create samSocketManager
        samSessionOptions = {'inbound.nickname':self.config.getStr('i2p','samDisplayName'),
                             'inbound.quantity':self.config.getStr('i2p','samNumOfTunnelsIn'),
                             'inbound.backupQuantity':self.config.getStr('i2p','samNumOfBackupTunnelsIn'),
                             'inbound.length':self.config.getStr('i2p','samTunnelLengthIn'),
                             'inbound.lengthVariance':self.config.getStr('i2p','samTunnelLengthVarianceIn'),
                             'inbound.allowZeroHop':self.config.getStr('i2p','samZeroHopsIn'),
                             'outbound.quantity':self.config.getStr('i2p','samNumOfTunnelsOut'),
                             'outbound.backupQuantity':self.config.getStr('i2p','samNumOfBackupTunnelsOut'),
                             'outbound.length':self.config.getStr('i2p','samTunnelLengthOut'),
                             'outbound.lengthVariance':self.config.getStr('i2p','samTunnelLengthVarianceOut'),
                             'outbound.allowZeroHop':self.config.getStr('i2p','samZeroHopsOut')}
                    
        self.samSockManager = I2PSocketManager(log='SamSocketManager', asmLog='AsyncSocketManager')
        self.destNum = self.samSockManager.addDestination(self.config.get('i2p','samIp'),
                                                          self.config.get('i2p','samPort'),
                                                          self.config.get('i2p','samSessionName'),
                                                          'tcp', 'both', samSessionOptions,
                                                          defaultOutMaxQueueSize=5120)
        
        #create event scheduler
        self.eventSched = EventScheduler()
        
        #create traffic related classes
        self.inLimiter = RefillingQuotaLimiter(self.eventSched, self.config.get('network','downSpeedLimit'))
        self.outLimiter = RefillingQuotaLimiter(self.eventSched, self.config.get('network','upSpeedLimit'))
        self.inRate = Measure(self.eventSched, 60)
        self.outRate = Measure(self.eventSched, 60)
        
        #create connection related classes
        self.peerPool = PeerPool()
        self.connHandler = ConnectionHandler(self.config, self.peerPool, self.samSockManager.select, self.eventSched,\
                                             self.inLimiter, self.outLimiter, self.peerId)
        self.connListener = ConnectionListener(self.eventSched, self.connHandler, self.peerPool, self.destNum, self.samSockManager, self.peerId)
        self.connBuilder = ConnectionBuilder(self.eventSched, self.connHandler, self.peerPool, self.destNum, self.samSockManager, self.peerId)
        
        #create own address watcher class
        self.ownAddrWatcher = OwnAddressWatcher(self.destNum, self.samSockManager)
        
        #create http requester class
        self.httpRequester = HttpRequester(self.eventSched, self.destNum, self.samSockManager)
        
        #add config callbacks
        callbackSamAddressOptions = {('i2p','samIp'):'ip',
                                     ('i2p','samPort'):'port'}
                                    
        callbackSamSessionOptions = {('i2p','samDisplayName'):'inbound.nickname',
                                     ('i2p','samNumOfTunnelsIn'):'inbound.quantity',
                                     ('i2p','samNumOfBackupTunnelsIn'):'inbound.backupQuantity',
                                     ('i2p','samTunnelLengthIn'):'inbound.length',
                                     ('i2p','samTunnelLengthVarianceIn'):'inbound.lengthVariance',
                                     ('i2p','samZeroHopsIn'):'inbound.allowZeroHop',
                                     ('i2p','samNumOfTunnelsOut'):'outbound.quantity',
                                     ('i2p','samNumOfBackupTunnelsOut'):'outbound.backupQuantity',
                                     ('i2p','samTunnelLengthOut'):'outbound.length',
                                     ('i2p','samTunnelLengthVarianceOut'):'outbound.lengthVariance',
                                     ('i2p','samZeroHopsOut'):'outbound.allowZeroHop'}
                                    
        self.config.addCallback(callbackSamAddressOptions.keys(), self.samSockManager.changeSessionAddress,
                                funcArgs=[self.destNum], funcKw={'reconnect':True}, valueArgPlace=1,
                                callType='item-funcKwSingle', optionTranslationTable=callbackSamAddressOptions, callWithAllOptions=True)
                                
        self.config.addCallback((('i2p','samSessionName'),), self.samSockManager.changeSessionName,
                                funcArgs=[self.destNum], funcKw={'reconnect':True}, valueArgPlace=1)
        
                            
        self.config.addCallback(callbackSamSessionOptions.keys(), self.samSockManager.replaceSessionOptions,
                                funcArgs=[self.destNum], funcKw={'reconnect':True}, valueArgPlace=1,
                                callType='item-dictArg', optionTranslationTable=callbackSamSessionOptions, callWithAllOptions=True)
        
        self.config.addCallback((('network', 'downSpeedLimit'),), self.inLimiter.changeRate)
        self.config.addCallback((('network', 'upSpeedLimit'),), self.outLimiter.changeRate)
        
        #queue related structures
        self.torrentId = 1
        self.torrentQueue = []
        self.torrentHashes = set()
        self.torrentInfo = {}
        self._loadTorrentQueue()
        
        #lock
        self.lock = threading.Lock()
        
        
    ##internal functions - state
    
    def _updateStoredObj(self, obj):
        if type(obj)==tuple:
            #pre 0.0.4
            self.log.info('Changing type of saved state obj from tuple to dict')
            obj = {'queue':obj[0],
                   'version':obj[1]}
                
        currentVersion = tuple((int(digit) for digit in VERSION.split('.')))
        objVersion = tuple((int(digit) for digit in obj['version'].split('.')))
        
        if objVersion < currentVersion:
            #need to do some updates
            if objVersion < (0,0,4):
                #pre 0.0.4, add infohash set
                self.log.info('Updating state obj to the v0.0.4+ format')
                newQueue = []
                infohashes = set()
                for queueElement in obj['queue']:
                    #process on old queue job
                    failureMsg, torrent = self._getTorrentObj(queueElement['id'])
                    if failureMsg is not None:
                        #failure reading or parsing torrent file
                        self.log.warn("Failed to add torrent %i, reason: %s", queueElement['id'], failureMsg)
                    else:
                        #ok so far
                        infohash = torrent.getTorrentHash()
                        if infohash in infohashes:
                            #duplicate
                            self.log.warn("Torrent %i is a duplicate, ignoring it!")
                        else:
                            #go on
                            infohashes.add(infohash)
                            newQueue.append(queueElement)
                
                #adapt obj
                obj['queue'] = newQueue
                obj['version'] = '0.0.4'
                objVersion = (0,0,4)
            
            self.persister.store('MultiBt-torrentQueue', obj)
        return obj
    
        
    def _storeState(self):
        self.persister.store('MultiBt-torrentQueue', {'queue':self.torrentQueue, 'version':VERSION})
        
 
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
        obj = self.persister.get('MultiBt-torrentQueue', ({'queue':[], 'version':VERSION}))
        obj = self._updateStoredObj(obj)
        
        #add torrents to queue
        oldQueue = obj['queue']
        activeTorrentIds = set()
        while len(oldQueue) > 0:
            #not empty, process next queue element
            queueElement = oldQueue[0]
            del oldQueue[0]
            
            #increase id if needed
            if self.torrentId <= queueElement['id']:
                self.torrentId = queueElement['id'] + 1
            
            #add torrent to queue
            failureMsg = self._addTorrent(queueElement['id'], queueElement['dataPath'], False)
            if failureMsg is None:
                #success
                activeTorrentIds.add(queueElement['id'])
            else:
                #failed to add
                self.log.warn("Failed to add torrent %i, reason: %s", queueElement['id'], failureMsg)
                
        #save new queue to disk
        self._storeState()
                
        #cleanup persister
        btKeyMatcher = re.compile('^Bt([0-9]+)-')
        btKeys = self.persister.keys('^Bt[0-9]+-')
        for key in btKeys:
            matchObj = btKeyMatcher.match(key)
            assert matchObj is not None, 'passed key regex but still not valid: "%s"' % (key,)
            torrentId = int(matchObj.group(1))
            if torrentId in activeTorrentIds:
                self.log.debug('Key "%s" belongs to an active torrent, not removing it', key)
            else:
                self.log.info('Key "%s" belongs to an inactive torrent, removing it', key)
                self.persister.remove(key, strict=False)
                    
                    
    def _moveUp(self, torrentIndex):
        if not torrentIndex == 0:
            queueElement = self.torrentQueue[torrentIndex]
            del self.torrentQueue[torrentIndex]
            self.torrentQueue.insert(torrentIndex-1, queueElement)
            self._storeState()
            
            
    def _moveDown(self, torrentIndex):
        if not torrentIndex == len(self.torrentQueue)-1:
            queueElement = self.torrentQueue[torrentIndex]
            del self.torrentQueue[torrentIndex]
            self.torrentQueue.insert(torrentIndex+1, queueElement)
            self._storeState()
    
    
    ##internal functions - torrent
    
    def _getTorrentFilePath(self, torrentId):
        return os.path.join(self.progPath, 'Torrents', str(torrentId)+'.torrent')
    
    
    def _getTorrentObj(self, torrentId):
        failureMsg = None
        torrent = None
        
        #try to load torrent data from the usual place
        torrentFilePath = self._getTorrentFilePath(torrentId)
        self.log.debug('Torrent %i: trying to read torrent data from "%s"', torrentId, torrentFilePath)
        try:
            fl = open(torrentFilePath, 'rb')
            with fl:
                torrentFileData = fl.read()
        except:
            failureMsg = 'Could not read torrent file from "%s"' % encodeStrForPrinting(torrentFilePath)
    
        if failureMsg is None:
            #successfully read the torrent data
            self.log.debug('Torrent %i: trying to parse read torrent data', torrentId)
            torrent = Torrent()
            try:
                torrent.load(torrentFileData)
            except TorrentException, e:
                failureMsg = e.reason
            except:
                failureMsg = 'Failed to parse torrent file "%s"!\nTraceback: %s' % (encodeStrForPrinting(torrentFilePath), logTraceback())
        
        return failureMsg, torrent
    

    def _addTorrent(self, torrentId, torrentDataPath, storeState=True):
        failureMsg, torrent = self._getTorrentObj(torrentId)
        if failureMsg is None:
            #valid torrent data
            infohash = torrent.getTorrentHash()
            if infohash in self.torrentHashes:
                #torrent is already on the queue
                failureMsg = 'Torrent is already queued'
            else:
                #torrent is not on the queue
                self.torrentHashes.add(infohash)
                
                self.log.debug('Torrent %i: creating bt class', torrentId)
                btObj = Bt(self.config, self.eventSched, self.httpRequester, self.ownAddrWatcher.getOwnAddr, self.peerId, self.persister, self.inRate, self.outRate,
                           self.peerPool, self.connBuilder, self.connListener, self.connHandler, torrent, 'Bt'+str(torrentId), torrentDataPath)
                
                #add to queue
                self.log.debug('Torrent %i: adding to queue', torrentId)
                self.torrentInfo[torrentId] = {'obj':btObj,
                                               'hash':infohash}
                                            
                self.torrentQueue.append({'id':torrentId,
                                          'state':'stopped',
                                          'dataPath':torrentDataPath})
                
                if storeState:
                    #save updated queue to disk
                    self.log.debug('Torrent %i: saving queue to disk', torrentId)
                    self._storeState()
                
        if failureMsg is not None:
            self.log.info("Failed to add torrent, reason: %s", failureMsg)
                
        return failureMsg
    
    
    def _startTorrent(self, torrentId):
        #start torrent
        self.torrentInfo[torrentId]['obj'].start()
        
        #adapt queue
        queueIndex = self._getQueueIndex(torrentId)
        self.torrentQueue[queueIndex]['state'] = 'running'
        self._storeState()
        
        
    def _stopTorrent(self, torrentId):
        #really stop torrent
        self.torrentInfo[torrentId]['obj'].stop()
        
        #adapt queue
        queueIndex = self._getQueueIndex(torrentId)
        self.torrentQueue[queueIndex]['state'] = 'stopped'
        self._storeState()
        
        
    def _removeTorrent(self, torrentId):
        #stop torrent
        self.torrentInfo[torrentId]['obj'].remove()
        
        #remove from hash set
        self.torrentHashes.remove(self.torrentInfo[torrentId]['hash'])
        
        #delete torrent entry
        del self.torrentInfo[torrentId]
        
        #remove from queue
        queueIndex = self._getQueueIndex(torrentId)
        del self.torrentQueue[queueIndex]
        self._storeState()
        
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
            with fl:
                fl.write(torrentFileData)
        except:
            self.lock.release()
            raise MultiBtException('Failed to save torrent data to "%s"', encodeStrForPrinting(torrentFilePath))
        
        #add to queue
        failureMsg = self._addTorrent(torrentId, torrentDataPath)
        self.lock.release()
        if failureMsg is not None:
            raise MultiBtException(failureMsg)
        else:
            return torrentId
        
        
    def startTorrent(self, torrentId):
        self.lock.acquire()
        if torrentId in self.torrentInfo:
            self._startTorrent(torrentId)
        self.lock.release()
    
    
    def stopTorrent(self, torrentId):
        self.lock.acquire()
        if torrentId in self.torrentInfo:
            self._stopTorrent(torrentId)
        self.lock.release()
    
    
    def removeTorrent(self, torrentId):
        self.lock.acquire()
        if torrentId in self.torrentInfo:
            self._removeTorrent(torrentId)
        self.lock.release()
        
        
    def isTorrentStarted(self, torrentId):
        self.lock.acquire()
        started = False
        if torrentId in self.torrentInfo:
            torrentIndex = self._getQueueIndex(torrentId)
            if self.torrentQueue[torrentIndex]['state'] == 'running':
                started = True
        self.lock.release()
        return started
        
        
    ##external functions - queue
    
    def moveUp(self, torrentId):
        self.lock.acquire()
        if torrentId in self.torrentInfo:
            torrentIndex = self._getQueueIndex(torrentId)
            self._moveUp(torrentIndex)
        self.lock.release()
    
    
    def moveDown(self, torrentId):
        self.lock.acquire()
        if torrentId in self.torrentInfo:
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
                stats['bt'] = self.torrentInfo[btStats]['obj'].getStats(wantedTorrentStats)
                if wantedTorrentStats.get('queue', False):
                    #queue stats
                    stats['bt'].update(self._getTorrentStats(btStats))
                
            else:
                #wants all
                statList = []
                for torrentId in self.torrentInfo.iterkeys():
                    #get stats for each torrent
                    statItem = self.torrentInfo[torrentId]['obj'].getStats(wantedTorrentStats)
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
        for btInfo in self.torrentInfo.itervalues():
            btInfo['obj'].shutdown()
        
        #stop http requester
        self.log.info("Stopping http requester")
        self.httpRequester.stop()
        
        #stop all connection related classes
        self.log.info("Stopping all connection related classes")
        self.peerPool.stop()
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
