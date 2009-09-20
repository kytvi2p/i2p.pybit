"""
Copyright 2009  Blub
BtQueueManager, a class for managing a torrent queue (including the actual Bt-objects).
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

##builtin
from __future__ import with_statement
import logging
import os
import re
import threading


##own
from Bt import Bt
from BtQueue import BtQueue
from HttpUtilities import splitUrl, HttpUtilitiesException
from Torrent import Torrent, TorrentException
from TorrentHttpFetch import TorrentHttpFetch
from Utilities import encodeStrForPrinting, logTraceback


class BtQueueManagerException(Exception):
    def __init__(self, reason, *args):
        self.reason = reason % args
        Exception.__init__(self, self.reason)
        
        
        
        
class BtQueueManager:
    def __init__(self, choker, config, connBuilder, connListener, connHandler, eventSched, httpRequester, inRate, outRate,
                 ownAddrWatcher, peerId, peerPool, persister, progPath, curVersion):
        
        #given classes
        self.choker = choker
        self.config = config
        self.connBuilder = connBuilder
        self.connListener = connListener
        self.connHandler = connHandler
        self.eventSched = eventSched
        self.httpRequester = httpRequester
        self.inRate = inRate
        self.outRate = outRate
        self.ownAddrWatcher = ownAddrWatcher
        self.peerId = peerId
        self.peerPool = peerPool
        self.persister = persister
        self.progPath = progPath
        self.curVersion = curVersion
        
        #log
        self.log = logging.getLogger('BtQueueManager')
        
        #lock
        self.lock = threading.Lock()
        
        #queue
        self.queue = BtQueue(self.curVersion, self.persister)
        self.queueJobs = {}
        self._load()
        
        
    ##internal functions - loading
    
    def _load(self):
        #restart all queued jobs
        queueIds = self.queue.queueGet()
        queueInfo = self.queue.infoGetAll()
        for queueId in queueIds:
            #load one job
            failureMsg, obj = self._getJobObj(queueId, queueInfo[queueId])
            if failureMsg is None:
                #success
                self.queueJobs[queueId] = obj
            else:
                #failed to add
                self.log.warn("Failed to add queue job %i (type %s), reason: %s", queueId, queueInfo[queueId]['type'], failureMsg)
                self.queue.queueRemove(queueId)
                
        #cleanup persister
        btKeyMatcher = re.compile('^Bt([0-9]+)-')
        btKeys = self.persister.keys('^Bt[0-9]+-')
        for key in btKeys:
            matchObj = btKeyMatcher.match(key)
            assert matchObj is not None, 'passed key regex but still not valid: "%s"' % (key,)
            queueId = int(matchObj.group(1))
            if self.queue.queueContains(queueId):
                self.log.debug('Key "%s" belongs to an active queue job, not removing it', key)
            else:
                self.log.info('Key "%s" belongs to an inactive queue job, removing it', key)
                self.persister.remove(key, strict=False)
    
    
    ##internal functions - torrents
    
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
        except (IOError, OSError):
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
                failureMsg = 'Failed to parse torrent file "%s"!\nTraceback: %s' % (encodeStrForPrinting(torrentFilePath), encodeStrForPrinting(logTraceback()))
        
        return failureMsg, torrent
    

    def _getBtObj(self, torrentId, torrentDataPath):
        btObj = None
        infoHash = None
        failureMsg, torrent = self._getTorrentObj(torrentId)
        if failureMsg is None:
            #valid torrent data
            infohash = torrent.getTorrentHash()
            if self.queue.setContains('torrentHash', infohash):
                #torrent is already on the queue
                failureMsg = 'Torrent is already queued'
            else:
                #torrent is not on the queue
                self.queue.setAdd('torrentHash', infohash)
                self.log.debug('Torrent %i: creating bt class', torrentId)
                btObj = Bt(self.config, self.eventSched, self.httpRequester, self.ownAddrWatcher.getOwnAddr, self.peerId, self.persister, self.inRate, self.outRate,
                           self.peerPool, self.connBuilder, self.connListener, self.connHandler, self.choker, torrent, 'Bt'+str(torrentId), torrentDataPath, self.curVersion)
                
        return failureMsg, btObj
    
    
    ##internal functions - http job
    
    def _getHttpFetchObj(self, torrentId, torrentDataPath, torrentUrlStr):
        httpFetchObj = None
        failureMsg = None
        try:
            torrentUrlSplit = splitUrl(torrentUrlStr)
        except HttpUtilitiesException, e:
            failureMsg = e.reason
            
        if failureMsg is None:
            if self.queue.setContains('torrentUrl', torrentUrlStr):
                #this url is already getting fetched
                failureMsg = 'Fetch of this url is already queued'
            else:
                #not yet on the queue
                self.queue.setAdd('torrentUrl', torrentUrlStr)
                self.log.debug('Torrent %i: creating http fetch class', torrentId)
                httpFetchObj = TorrentHttpFetch(self.config, self.eventSched, self.httpRequester, 'Bt'+str(torrentId), torrentUrlSplit, torrentUrlStr, self.finishedFetch, [torrentId])
            
        return failureMsg, httpFetchObj
    
    
    def _replaceHttpFetchObj(self, queueId, torrentData):
        failureMsg = None
        info = self.queue.infoGet(queueId)
        
        #save torrent file
        torrentFilePath = self._getTorrentFilePath(queueId)
        try:
            fl = open(torrentFilePath, 'wb')
            with fl:
                fl.write(torrentData)
        except (IOError, OSError):
            failureMsg = 'Failed to save torrent data to "%s"' % (encodeStrForPrinting(torrentFilePath),)
        
        if failureMsg is None:
            #create bt object
            failureMsg, btObj = self._getBtObj(queueId, info['dataPath'])
            
            if failureMsg is None:
                #replace obj
                self.queueJobs[queueId].shutdown()
                self.queueJobs[queueId] = btObj
                
                #remove url from set
                self.queue.setRemove('torrentUrl', info['url'])
                
                #modify info
                del info['url']
                info['type'] = 'bt'
                self.queue.setInfo(queueId, info)
        return failureMsg
    
    
    ##internal functions - queue
    
    def _getJobObj(self, queueId, queueInfo):
        if queueInfo['type'] == 'bt':
            #normal torrent job
            failureMsg, obj = self._getBtObj(queueId, queueInfo['dataPath'])
        elif queueInfo['type'] == 'httpFetch':
            #http fetch of torrent file
            failureMsg, obj = self._getHttpFetchObj(queueId, queueInfo['dataPath'], queueInfo['url'])
        else:
            #unknown type
            failureMsg = 'Internal error: Unknown job type "%s"' % (queueInfo['type'],)
            obj = None
        return failureMsg, obj
    
    
    def _addJob(self, queueId, queueInfo, obj=None):
        if obj is not None:
            failureMsg = None
        else:
            failureMsg, obj = self._getJobObj(queueId, queueInfo)
        if failureMsg is None:
            self.queue.queueAdd(queueId, queueInfo)
            self.queueJobs[queueId] = obj
        return failureMsg
    

    def _startJob(self, queueId):
        #start queued job
        self.queueJobs[queueId].start()
        
        
    def _stopJob(self, queueId):
        #stop queued job
        self.queueJobs[queueId].stop()
        
        
    def _removeJob(self, queueId):
        #remove queued job
        obj = self.queueJobs[queueId]
        del self.queueJobs[queueId]
        obj.remove()
        
        #cleanup queue
        info = self.queue.infoGet(queueId)
        self.queue.queueRemove(queueId)
        if info['type'] == 'bt':
            self.queue.setRemove('torrentHash', obj.getInfohash())
            try:
                os.remove(self._getTorrentFilePath(queueId))
            except (IOError, OSError):
                pass
            
        elif info['type'] == 'httpFetch':
            self.queue.setRemove('torrentUrl', info['url'])
            
    
    ##external functions - torrents
    
    def addTorrentByFile(self, torrentFileData, torrentDataPath):
        with self.lock:
            #get id
            torrentId = self.queue.queueNextId()
            
            #store torrent file in torrent directory
            torrentFilePath = self._getTorrentFilePath(torrentId)
            try:
                fl = open(torrentFilePath, 'wb')
                with fl:
                    fl.write(torrentFileData)
            except (IOError, OSError):
                raise BtQueueManagerException('Failed to save torrent data to "%s"', encodeStrForPrinting(torrentFilePath))
            
            #add to queue
            info = {'type':'bt',
                    'dataPath':torrentDataPath}
            failureMsg = self._addJob(torrentId, info)
            if failureMsg is not None:
                self.log.info("Failed to add torrent, reason: %s", failureMsg)
                raise BtQueueManagerException(failureMsg)
            return torrentId
        
        
    def addTorrentByUrl(self, torrentUrl, torrentDataPath):
        with self.lock:
            #get id
            torrentId = self.queue.queueNextId()
            
            #add to queue
            info = {'type':'httpFetch',
                    'dataPath':torrentDataPath,
                    'url':torrentUrl}
            failureMsg = self._addJob(torrentId, info)
            if failureMsg is not None:
                self.log.info("Failed to add torrent, reason: %s", failureMsg)
                raise BtQueueManagerException(failureMsg)
            return torrentId
        
        
    ##external functions - http fetches
    
    def finishedFetch(self, result, queueId):
        with self.lock:
            if queueId in self.queueJobs:
                if result['success'] == True:
                    #fetch succeded
                    failureMsg = self._replaceHttpFetchObj(queueId, result['data'])
                    if failureMsg is not None:
                        self.log.info("Torrent %i: failed to add fetched torrent, reason: %s", queueId, failureMsg)
                        self.queueJobs[queueId].setState('error (%s)' % (failureMsg.split('\n')[0],))
        
        
    ##external functions - queue
        
    def startJob(self, queueId):
        with self.lock:
            if queueId in self.queueJobs:
                self._startJob(queueId)
    
    
    def stopJob(self, queueId):
        with self.lock:
            if queueId in self.queueJobs:
                self._stopJob(queueId)
    
    
    def removeJob(self, queueId):
        with self.lock:
            if queueId in self.queueJobs:
                self._removeJob(queueId)
                
                
    def moveJob(self, queueId, steps):
        with self.lock:
            if queueId in self.queueJobs:
                self.queue.queueMove(queueId, steps)
                
                
    ##external functions - torrent actions
    
    def setFilePriority(self, torrentId, fileIds, priority):
        with self.lock:
            if torrentId in self.queueJobs:
                obj = self.queueJobs[torrentId]
                if isinstance(obj, Bt):
                    obj.setFilePriority(fileIds, priority)
        
        
    def setFileWantedFlag(self, torrentId, fileIds, wanted):
        with self.lock:
            if torrentId in self.queueJobs:
                obj = self.queueJobs[torrentId]
                if isinstance(obj, Bt):
                    obj.setFileWantedFlag(fileIds, wanted)
        
        
    def setSuperSeeding(self, torrentId, enabled):
        with self.lock:
            if torrentId in self.queueJobs:
                obj = self.queueJobs[torrentId]
                if isinstance(obj, Bt):
                    obj.setSuperSeeding(enabled)
    
    
    ##external functions - stats
    
    def getStats(self, queueId, wantedTorrentStats):
        with self.lock:
            stats = {}
            if isinstance(queueId, int) or isinstance(queueId, long):
                #single bt stats
                stats = self.queueJobs[queueId].getStats(wantedTorrentStats)
                if wantedTorrentStats.get('queue', False):
                    #queue stats
                    stats.update(self.queue.getStats(queueId))
            else:
                #wants all
                stats = []
                for queueId in self.queue.queueGet():
                    #get stats for each torrent
                    statItem = self.queueJobs[queueId].getStats(wantedTorrentStats)
                    if wantedTorrentStats.get('queue', False):
                        #queue stats
                        statItem.update(self.queue.getStats(queueId))
                    stats.append(statItem)
        return stats
                
    ##external functions - other
    
    def shutdown(self):
        #stop all jobs without modifying the queue
        with self.lock:
            self.log.info("Stopping all bt jobs")
            for job in self.queueJobs.itervalues():
                job.shutdown()
            self.queueJobs = {}