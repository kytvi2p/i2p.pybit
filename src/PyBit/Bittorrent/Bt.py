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

from Choker import Choker
from GlobalStatus import GlobalStatus
from Measure import Measure
from Requester import Requester
from Storage import Storage, StorageException
from TrackerRequester import TrackerRequester
from Utilities import logTraceback


class Bt:
    def __init__(self, config, eventSched, httpRequester, ownAddrFunc, peerId, pInMeasure, pOutMeasure,
                 connPool, connBuilder, connListener, connHandler, torrent, torrentIdent, torrentDataPath):
        ##global stuff
        self.config = config
        self.connPool = connPool
        self.connBuilder = connBuilder
        self.connListener = connListener
        self.connHandler = connHandler
        
        ##own stuff
        self.log = logging.getLogger(torrentIdent)
        self.torrent = torrent
        self.torrentIdent = torrentIdent
        
        self.log.debug("Creating measure classes")
        self.inRate = Measure(eventSched, 60, [pInMeasure])
        self.outRate = Measure(eventSched, 60, [pOutMeasure])
        
        self.log.debug("Creating storage class")
        self.storage = Storage(torrentIdent, self.torrent, torrentDataPath)
        
        self.log.debug("Creating global status class")
        self.globalStatus = GlobalStatus(self.torrent.getTotalAmountOfPieces())
        self.log.debug("Creating requester class")
        self.requester = Requester(self.torrentIdent, self.globalStatus, self.storage, self.torrent)
        self.log.debug("Creating tracker requester class")
        self.trackerRequester = TrackerRequester(eventSched, peerId, self.connPool, ownAddrFunc, httpRequester,
                                                 self.inRate, self.outRate, self.storage, self.torrent, self.torrentIdent)
        self.log.debug("Creating choker class")
        self.choker = Choker(self.torrentIdent, eventSched, self.connHandler, self.storage.getStatus())
        
        ##status
        self.started = False
        self.paused = False
        self.stopped = True
        
        ##locks
        self.loadLock = threading.Lock()
        self.lock = threading.Lock()
        
    
    def _start(self):
        self.loadLock.acquire()
        try:
            loaded = False
            if self.storage.isLoaded():
                loaded = True
                self.log.debug("Storage already loaded, skipping hashing")
            else:
                try:
                    self.log.debug("Loading ...")
                    self.storage.load()
                    self.log.debug("Reseting requester")
                    self.requester.reset()
                    loaded = True
                    
                except StorageException:
                    #failure while loading
                    self.log.error("Loading failed:\n%s", logTraceback())
                    
            if loaded:
                #finished loading, add to handlers
                self.log.debug("Adding us to connection handler")
                self.connHandler.addTorrent(self.torrentIdent, self.torrent, self.globalStatus, self.inRate, self.outRate, self.storage, self.requester)
                
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
            
        self.loadLock.release()
        
    
    def _pause(self):
        self.log.debug("Aborting storage loading just in case")
        self.storage.abortLoad()
        self.loadLock.acquire()
        self.loadLock.release()
        
        if self.started:
            #were already running
            self.started = False
            
            self.log.debug("Stopping choker")
            self.choker.stop()
            
            self.log.debug("Pausing tracker requester")
            self.trackerRequester.pause()
            
            self.log.debug("Removing us from connection builder")
            self.connBuilder.removeTorrent(self.torrentIdent)
            
            self.log.debug("Removing us from connection listener")
            self.connListener.removeTorrent(self.torrent.getTorrentHash())
            
            self.log.debug("Removing us from connection handler")
            self.connHandler.removeTorrent(self.torrentIdent)
        
        
    def _stop(self):
        if self.paused:
            #already paused, only need to stop the tracker requester and clear some infos
            self.log.debug("Stopping tracker requester")
            self.trackerRequester.stop()
            
            self.log.debug("Removing all infos related to use from connection pool")
            self.connPool.clear(self.torrentIdent)
            
        else:
            #still running or loading
            self.log.debug("Aborting storage loading just in case")
            self.storage.abortLoad()
            self.loadLock.acquire()
            self.loadLock.release()
            
            if self.started:
                #were already running
                self.started = False
                
                self.log.debug("Stopping choker")
                self.choker.stop()
                
                self.log.debug("Stopping tracker requester")
                self.trackerRequester.stop()
                
                self.log.debug("Removing us from connection builder")
                self.connBuilder.removeTorrent(self.torrentIdent)
                
                self.log.debug("Removing us from connection listener")
                self.connListener.removeTorrent(self.torrent.getTorrentHash())
                
                self.log.debug("Removing us from connection handler")
                self.connHandler.removeTorrent(self.torrentIdent)
                
                self.log.debug("Removing all infos related to us from connection pool")
                self.connPool.clear(self.torrentIdent)
        

    def start(self):
        self.lock.acquire()
        if self.paused or self.stopped:
            self.paused = False
            self.stopped = False
            thread = threading.Thread(target=self._start)
            thread.start()
        self.lock.release()
        
    def pause(self):
        self.lock.acquire()
        if not (self.paused or self.stopped):
            self._pause()
            self.paused = True
            self.stopped = False
        self.lock.release()
        
        
    def stop(self):
        self.lock.acquire()
        if not self.stopped:
            self._stop()
            self.paused = False
            self.stopped = True
        self.lock.release()
        
        
    def getStats(self, wantedStats):
        self.lock.acquire()
        stats = {}
        
        #connections
        if wantedStats.get('connections', False):
            stats['connections'] = self.connHandler.getStats(self.torrentIdent)
        
        #peers
        if wantedStats.get('peers', False):
            stats.update(self.connPool.getStats(self.torrentIdent))
            
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