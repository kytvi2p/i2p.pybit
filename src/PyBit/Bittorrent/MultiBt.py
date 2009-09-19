"""
Copyright 2009  Blub

MultiBt, a class which is used as an inteface between any kind of user interface and the bittorrent classes.
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
from BtQueueManager import BtQueueManager, BtQueueManagerException
from Choker import Choker
from Conversion import shortIntToBinary
from ConnectionBuilder import ConnectionBuilder
from ConnectionHandler import ConnectionHandler
from ConnectionListener import ConnectionListener
from PeerPool import PeerPool
from EventScheduler import EventScheduler
from HttpRequester import HttpRequester
from Limiter import SelfRefillingQuotaLimiter
from Measure import Measure
from OwnAddressWatcher import OwnAddressWatcher
from Utilities import generateRandomBinary, logTraceback
from PySamLib.I2PSocketManager import I2PSocketManager

#DEBUG
#import gc


class MultiBtException(Exception):
    def __init__(self, reason, *args):
        self.reason = reason % args
        Exception.__init__(self, self.reason)


class MultiBt:
    def __init__(self, config, persister, progPath, version):
        self.config = config
        self.persister = persister
        self.progPath = progPath
        self.version = version
        
        #DEBUG
        #gc.set_debug(gc.DEBUG_UNCOLLECTABLE)
        #gc.set_debug(gc.DEBUG_LEAK)
        #gc.set_debug(gc.DEBUG_COLLECTABLE | gc.DEBUG_UNCOLLECTABLE | gc.DEBUG_INSTANCES | gc.DEBUG_OBJECTS)
        
        #log
        self.log = logging.getLogger('MultiBt')
        
        #generate peerid
        versionDigits = self.version.split('.')
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
        self.inLimiter = SelfRefillingQuotaLimiter(self.eventSched, self.config.get('network','downSpeedLimit'))
        self.outLimiter = SelfRefillingQuotaLimiter(self.eventSched, self.config.get('network','upSpeedLimit'))
        self.inRate = Measure(self.eventSched, 60)
        self.outRate = Measure(self.eventSched, 60)
        
        #create connection related classes
        self.peerPool = PeerPool()
        self.connHandler = ConnectionHandler(self.config, self.peerPool, self.samSockManager.select, self.eventSched,\
                                             self.inLimiter, self.outLimiter, self.peerId)
        self.connListener = ConnectionListener(self.eventSched, self.connHandler, self.peerPool, self.destNum, self.samSockManager, self.peerId)
        self.connBuilder = ConnectionBuilder(self.eventSched, self.connHandler, self.peerPool, self.destNum, self.samSockManager, self.peerId)
        
        #create choker
        self.choker = Choker(self.config, self.eventSched, self.connHandler)
        
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
        
        #queue
        self.queue = BtQueueManager(self.choker, self.config, self.connBuilder, self.connListener, self.connHandler, self.eventSched,
                                    self.httpRequester, self.inRate, self.outRate, self.ownAddrWatcher, self.peerId, self.peerPool,
                                    self.persister, self.progPath, self.version)
                                    
        #lock
        self.lock = threading.Lock()
        
        
    ##external functions - torrents
    
    def addTorrentByFile(self, torrentFileData, torrentDataPath):
        with self.lock:
            try:
                torrentId = self.queue.addTorrentByFile(torrentFileData, torrentDataPath)
            except BtQueueManagerException, e:
                raise MultiBtException(e.reason)
            return torrentId
        
        
    def startTorrent(self, torrentId):
        with self.lock:
            self.queue.startJob(torrentId)
    
    
    def stopTorrent(self, torrentId):
        with self.lock:
            self.queue.stopJob(torrentId)
    
    
    def removeTorrent(self, torrentId):
        with self.lock:
            self.queue.removeJob(torrentId)
            
        
    def moveTorrent(self, torrentId, steps):
        with self.lock:
            self.queue.moveJob(torrentId, steps)
            
            
    ##external functions - torrent actions
    
    def setFilePriority(self, torrentId, fileIds, priority):
        with self.lock:
            self.queue.setFilePriority(torrentId, fileIds, priority)
        
        
    def setFileWantedFlag(self, torrentId, fileIds, wanted):
        with self.lock:
            self.queue.setFileWantedFlag(torrentId, fileIds, wanted)
        
        
    def setSuperSeeding(self, torrentId, enabled):
        with self.lock:
            self.queue.setSuperSeeding(torrentId, enabled)
        
    
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
            stats['bt'] = self.queue.getStats(btStats, wantedTorrentStats)
                
        self.lock.release()
        return stats
        
        
    ##external functions - other
    
    def stop(self):
        self.lock.acquire()
        self.log.info("Stopping")
        
        #stop all bt jobs without modifying the queue
        self.queue.shutdown()
        
        #stop http requester
        self.log.info("Stopping http requester")
        self.httpRequester.stop()
        
        #stop choker
        self.log.info("Stopping choker")
        self.choker.stop()
        
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
