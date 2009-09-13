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

import logging
import threading

from BtObjectPersister import BtObjectPersister
from Choker import Choker
from PieceStatus import PieceStatus
from Measure import Measure
from Requester import Requester
from Storage import Storage, StorageException
from TrackerRequester import TrackerRequester
from Utilities import logTraceback


class Bt:
    def __init__(self, config, eventSched, httpRequester, ownAddrFunc, peerId, persister, pInMeasure, pOutMeasure,
                 peerPool, connBuilder, connListener, connHandler, torrent, torrentIdent, torrentDataPath):
        ##global stuff
        self.config = config
        self.peerPool = peerPool
        self.connBuilder = connBuilder
        self.connListener = connListener
        self.connHandler = connHandler
        
        ##own stuff
        self.log = logging.getLogger(torrentIdent)
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
        
        self.log.debug("Creating requester class")
        self.requester = Requester(self.config, self.torrentIdent, self.pieceStatus, self.storage, self.torrent)
        
        self.log.debug("Creating tracker requester class")
        self.trackerRequester = TrackerRequester(eventSched, peerId, self.peerPool, ownAddrFunc, httpRequester,
                                                 self.inRate, self.outRate, self.storage, self.torrent, self.torrentIdent)
                                                
        self.log.debug("Creating choker class")
        self.choker = Choker(self.torrentIdent, eventSched, self.connHandler, self.storage.getStatus())
        
        ##calbacks
        self.log.debug("Adding callbacks")
        self._addCallbacks()
        
        ##status
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
            #either pausing or stopping and still running or loading
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
                
                self.log.debug("Stopping choker")
                self.choker.stop()
                
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
                self.connHandler.addTorrent(self.torrentIdent, self.torrent, self.pieceStatus, self.inRate, self.outRate, self.storage, self.requester)
                
                self.log.debug("Adding us to connection listener")
                self.connListener.addTorrent(self.torrentIdent, self.torrent.getTorrentHash())
                
                self.log.debug("Adding us to connection builder")
                self.connBuilder.addTorrent(self.torrentIdent, self.torrent.getTorrentHash())
                
                self.log.debug("Starting choker")
                self.choker.start()
                
                self.log.debug("Starting tracker requester")
                self.trackerRequester.start()
                
                self.started = True
                
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
        self.lock.release()
        
        
    def stop(self):
        #called when torrent is stopped
        self.lock.acquire()
        if not self.paused:
            self._halt('stop')
            self.paused = True
        self.lock.release()
        
        
    def shutdown(self):
        #called on shutdown
        self.lock.acquire()
        self._halt('shutdown')
        self.paused = False
        self.lock.release()
        
        
    def remove(self):
        #called when torrent is removed
        self.lock.acquire()
        self._halt('remove')
        self.paused = False
        self.lock.release()
        
        
    ##external functions - stats
        
        
    def getStats(self, wantedStats):
        self.lock.acquire()
        stats = {}
        
        #connections
        if wantedStats.get('connections', False):
            stats['connections'] = self.connHandler.getStats(self.torrentIdent)
        
        #peers
        if wantedStats.get('peers', False):
            stats.update(self.peerPool.getStats(self.torrentIdent))
            
        #transfer stats
        if wantedStats.get('transfer', False):
            stats['inPayloadBytes'] = self.inRate.getTotalTransferedPayloadBytes()
            stats['outPayloadBytes'] = self.outRate.getTotalTransferedPayloadBytes()
            stats['inRawSpeed'] = self.inRate.getCurrentRate()
            stats['outRawSpeed'] = self.outRate.getCurrentRate()
            
        if wantedStats.get('transferAverages', False):
            stats['avgInRawSpeed'] = self.inRate.getAverageRate() * 1024
            stats['avgOutRawSpeed'] = self.outRate.getAverageRate() * 1024
            
        #progress stats
        if wantedStats.get('progress', False):
            stats.update(self.storage.getStats())
            
        #torrent stats
        if wantedStats.get('torrent', False):
            stats.update(self.torrent.getStats())
            
        self.lock.release()
        return stats