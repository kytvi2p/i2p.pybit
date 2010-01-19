"""
Copyright 2009  Blub

Bt, a class for managing all activity which are needed to download/seed/... one torrent.
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

import threading

from BtObjectPersister import BtObjectPersister
from FilePriority import FilePriority
from Logger import Logger
from Measure import Measure
from PieceStatus import PieceStatus
from Requester import Requester
from Storage import Storage, StorageException
from SuperSeedingHandler import SuperSeedingHandler
from TrackerRequester import TrackerRequester
from Utilities import logTraceback


class Bt:
    def __init__(self, config, eventSched, httpRequester, ownAddrFunc, peerId, persister, pInMeasure, pOutMeasure,
                 peerPool, connBuilder, connListener, connHandler, choker, torrent, torrentIdent, torrentDataPath, version):
        ##global stuff
        self.config = config
        self.version = version
        self.peerPool = peerPool
        self.connBuilder = connBuilder
        self.connListener = connListener
        self.connHandler = connHandler
        self.choker = choker
        
        ##own stuff
        self.log = Logger('Bt', '%-6s - ', torrentIdent)
        self.torrent = torrent
        self.torrentIdent = torrentIdent
        
        self.log.debug("Creating object persister")
        self.btPersister = BtObjectPersister(persister, torrentIdent)
        
        self.log.debug("Creating measure classes")
        self.inRate = Measure(eventSched, 60, [pInMeasure])
        self.outRate = Measure(eventSched, 60, [pOutMeasure])
        self.inRate.stop()
        self.outRate.stop()
        
        self.log.debug("Creating storage class")
        self.storage = Storage(self.config, self.btPersister, torrentIdent, self.torrent, torrentDataPath)
        
        self.log.debug("Creating global status class")
        self.pieceStatus = PieceStatus(self.torrent.getTotalAmountOfPieces())
        
        self.log.debug("Creating file priority class")
        self.filePrio = FilePriority(self.btPersister, self.version, self.pieceStatus, self.storage.getStatus(),
                                     self.torrent, torrentIdent)
        
        self.log.debug("Creating requester class")
        self.requester = Requester(self.config, self.torrentIdent, self.pieceStatus, self.storage, self.torrent)
        
        self.log.debug("Creating tracker requester class")
        self.trackerRequester = TrackerRequester(self.config, self.btPersister, eventSched, peerId, self.peerPool, ownAddrFunc, httpRequester,
                                                 self.inRate, self.outRate, self.storage, self.torrent, self.torrentIdent, self.version)
        
        self.log.debug("Creating superseeding handler class")
        self.superSeedingHandler = SuperSeedingHandler(self.torrentIdent, self.btPersister, self.storage.getStatus(), self.pieceStatus)
        
        ##callbacks
        self.log.debug("Adding callbacks")
        self._addCallbacks()
        
        ##status
        self.state = 'stopped'
        self.started = False
        self.paused = True
        
        ##lock
        self.lock = threading.Lock()
        
    ##internal functions - callbacks
    
    def _addCallbacks(self):
        ownStatus = self.storage.getStatus()
        self.persistentStatusCallback = self.config.addCallback((('storage', 'persistPieceStatus'),), ownStatus.enablePersisting)
    
        
    def _removeCallbacks(self):
        self.config.removeCallback(self.persistentStatusCallback)
            
            
    ##internal functions - start/pause/stop - common
            
    def _halt(self, targetState):
        if self.paused and targetState in ('shutdown', 'remove'):
            #stopping and already paused, only need to stop the tracker requester and the callbacks
            self.log.debug("Removing callbacks")
            self._removeCallbacks()
                
            self.log.debug("Stopping tracker requester")
            self.trackerRequester.stop()
        
        else:
            #either stopping, removing or shutdown and still running or loading
            self.log.debug("Aborting storage loading just in case")
            self.storage.abortLoad()
            
            if self.started:
                #were already running
                self.started = False
                
                if targetState == 'stop':
                    self.log.debug("Pausing tracker requester")
                    self.trackerRequester.pause()
                else:
                    self.log.debug("Removing callbacks")
                    self._removeCallbacks()
                
                    self.log.debug("Stopping tracker requester")
                    self.trackerRequester.stop()
                
                self.log.debug("Removing us from choker")
                self.choker.removeTorrent(self.torrentIdent)
                
                self.log.debug("Removing us from connection builder")
                self.connBuilder.removeTorrent(self.torrentIdent)
                
                self.log.debug("Removing us from connection listener")
                self.connListener.removeTorrent(self.torrent.getTorrentHash())
                
                self.log.debug("Removing us from connection handler")
                self.connHandler.removeTorrent(self.torrentIdent)
                
                self.log.debug("Stopping transfer measurement")
                self.inRate.stop()
                self.outRate.stop()
                
        #shutdown/removal specific tasks which need to be done regardless of current status
        if targetState in ('shutdown', 'remove'):
            self.log.debug("Removing all infos related to us from connection pool")
            self.peerPool.clear(self.torrentIdent)
            
        if targetState == 'remove':
            self.log.debug('Removing all persisted objects of this torrent')
            self.btPersister.removeAll()
                
    
    ##internal functions - start/pause/stop - specific
    
    def _start(self, loadSuccess):
        try:
            if loadSuccess:
                #loading was successful, add to handlers
                self.log.debug("Reseting requester")
                self.requester.reset()
                    
                self.log.debug("Starting transfer measurement")
                self.inRate.start()
                self.outRate.start()
                
                self.log.debug("Adding us to connection handler")
                self.connHandler.addTorrent(self.torrentIdent, self.torrent, self.pieceStatus, self.inRate, self.outRate, self.storage, self.filePrio, self.requester, self.superSeedingHandler)
                
                self.log.debug("Adding us to connection listener")
                self.connListener.addTorrent(self.torrentIdent, self.torrent.getTorrentHash())
                
                self.log.debug("Adding us to connection builder")
                self.connBuilder.addTorrent(self.torrentIdent, self.torrent.getTorrentHash())
                
                self.log.debug("Adding us to choker")
                self.choker.addTorrent(self.torrentIdent, self.storage.getStatus(), self.superSeedingHandler)
                
                self.log.debug("Starting tracker requester")
                self.trackerRequester.start()
                
                self.started = True
                self.state = 'running'
                
        except:
            #something failed - hard
            self.log.error("Error in load function:\n%s", logTraceback())
                
                
    ##external functions - state

    def start(self):
        #called when torrent is started
        self.lock.acquire()
        if self.paused:
            self.paused = False
            if self.storage.isLoaded():
                self.log.debug("Storage already loaded, skipping hashing")
                self._start(True)
            else:
                self.storage.load(self._start)
                self.state = 'loading'
        self.lock.release()
        
        
    def stop(self):
        #called when torrent is stopped
        self.lock.acquire()
        if not self.paused:
            self._halt('stop')
            self.paused = True
            self.state = 'stopped'
        self.lock.release()
        
        
    def shutdown(self):
        #called on shutdown
        self.lock.acquire()
        self._halt('shutdown')
        self.paused = False
        self.state = 'stopped'
        self.lock.release()
        
        
    def remove(self):
        #called when torrent is removed
        self.lock.acquire()
        self._halt('remove')
        self.paused = False
        self.state = 'stopped'
        self.lock.release()
        
        
    ##external functions - stats
        
    def getStats(self, wantedStats):
        self.lock.acquire()
        stats = {}
        
        if wantedStats.get('state', False):
            stats['state'] = self.state
        
        #connections
        if wantedStats.get('connections', False):
            stats.update(self.connHandler.getStats(self.torrentIdent, connDetails=True))
            
        #files
        if wantedStats.get('files', False):
            stats['files'] = self.filePrio.getStats()
        
        #peers
        if wantedStats.get('peers', False) or wantedStats.get('connectionAverages', False):
            #get peer stats
            connAverages = wantedStats.get('connectionAverages', False)
            stats.update(self.peerPool.getStats(self.torrentIdent))
            stats.update(self.connHandler.getStats(self.torrentIdent, connSummary=True, connAverages=connAverages))
            stats.update(self.trackerRequester.getStats(trackerSummary=True))
            
            #normalise peer stats
            if stats['connectedLeeches'] > stats['knownLeeches']:
                stats['knownLeeches'] = stats['connectedLeeches']
            if stats['connectedSeeds'] > stats['knownSeeds']:
                stats['knownSeeds'] = stats['connectedSeeds']
            
            if stats['knownLeeches'] + stats['knownSeeds'] > stats['knownPeers']:
                stats['knownPeers'] = stats['knownLeeches'] + stats['knownSeeds']
            elif stats['knownLeeches'] + stats['knownSeeds'] < stats['knownPeers']:
                stats['knownLeeches'] += stats['knownPeers'] - stats['knownSeeds']
                
            #generate additional conn stats if necessary
            if connAverages:
                if stats['knownLeeches'] == 0:
                    stats['knownLeechesPerSeed'] = 0
                else:
                    stats['knownLeechesPerSeed'] = (stats['knownLeeches'] * 1.0) / stats['knownSeeds']
            
        #progress stats
        if wantedStats.get('progress', False):
            stats.update(self.storage.getStats())
                    
        #requests
        if wantedStats.get('requests', False):
            stats['requests'] = self.connHandler.getRequesterStats(self.torrentIdent)
            
        #tracker
        if wantedStats.get('tracker', False):
            stats.update(self.trackerRequester.getStats(trackerDetails=True))
            
        #transfer stats
        if wantedStats.get('transfer', False):
            stats['inRawBytes'] = self.inRate.getTotalTransferedBytes()
            stats['outRawBytes'] = self.outRate.getTotalTransferedBytes()
            stats['inPayloadBytes'] = self.inRate.getTotalTransferedPayloadBytes()
            stats['outPayloadBytes'] = self.outRate.getTotalTransferedPayloadBytes()
            stats['inRawSpeed'] = self.inRate.getCurrentRate()
            stats['outRawSpeed'] = self.outRate.getCurrentRate()
            stats['protocolOverhead'] = (100.0 * (stats['inRawBytes'] + stats['outRawBytes'] - stats['inPayloadBytes'] - stats['outPayloadBytes'])) / max(stats['inPayloadBytes'] + stats['outPayloadBytes'], 1.0)
            
        if wantedStats.get('transferAverages', False):
            stats['avgInRawSpeed'] = self.inRate.getAverageRate() * 1024
            stats['avgOutRawSpeed'] = self.outRate.getAverageRate() * 1024
            stats['avgInPayloadSpeed'] = self.inRate.getAveragePayloadRate() * 1024
            stats['avgOutPayloadSpeed'] = self.outRate.getAveragePayloadRate() * 1024
            
        #torrent stats
        if wantedStats.get('torrent', False):
            stats.update(self.torrent.getStats())
            stats['superSeeding'] = self.superSeedingHandler.isEnabled()
            
        self.lock.release()
        return stats
    
    
    ##external funcs - actions
    
    def setFilePriority(self, fileIds, priority):
        self.lock.acquire()
        for fileId in fileIds:
            self.filePrio.setFilePriority(fileId, priority)
        self.lock.release()
        
        
    def setFileWantedFlag(self, fileIds, wanted):
        self.lock.acquire()
        if self.started:
            #already running, need to go through the connection handler because of syncing issues
            self.connHandler.setFileWantedFlag(self.torrentIdent, fileIds, wanted)
        else:
            #not running
            for fileId in fileIds:
                self.filePrio.setFileWantedFlag(fileId, wanted)
        self.lock.release()
        
        
    def setSuperSeeding(self, enabled):
        self.lock.acquire()
        if not enabled == self.superSeedingHandler.isEnabled():
            if self.started:
                self.connHandler.setSuperSeeding(self.torrentIdent, enabled)
            else:
                self.superSeedingHandler.setEnabled(enabled)
        self.lock.release()
        
    ##external funcs - tracker actions
    
    def getTrackerInfo(self):
        self.lock.acquire()
        trackerInfo = self.trackerRequester.getTrackerInfo()
        self.lock.release()
        return trackerInfo
    
    
    def setTrackerInfo(self, newTrackerInfo):
        self.lock.acquire()
        self.trackerRequester.setTrackerInfo(newTrackerInfo)
        self.lock.release()
    
        
    ##external funcs - other
    
    def getInfohash(self):
        self.lock.acquire()
        infohash = self.torrent.getTorrentHash()
        self.lock.release()
        return infohash