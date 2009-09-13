"""
Copyright 2009  Blub

Choker, a class which handles choking and unchoking connection to other bittorrent clients.
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

from collections import deque
from random import random, sample
import logging
import threading

from Limiter import ManualQuotaLimiter


class Choker:
    def __init__(self, config, eventScheduler, connHandler):
        self.config = config
        self.sched = eventScheduler
        self.connHandler = connHandler
        
        self.torrents = {}
        
        self.randomSlotLimiter = ManualQuotaLimiter(1)
        self.normalSlotLimiter = ManualQuotaLimiter(1)
        self._setSlotLimits(self.config.get('choker','maxSlots'), self.config.get('choker','randomSlotRatio'))
        
        self.chokeEventId = None
        self.chokeIntervalConfigId = None
        self.slotLimitConfigId = None
        
        self.log = logging.getLogger('Choker')
        self.lock = threading.RLock()
        self._start()
        
        
    ##internal functions - torrent
        
    def _addTorrent(self, torrentIdent, ownStatus):
        assert (not torrentIdent in self.torrents), 'Torrent already added?!'
        self.torrents[torrentIdent] = {'ownStatus':ownStatus}
        self.randomSlotLimiter.addUser(torrentIdent)
        self.normalSlotLimiter.addUser(torrentIdent)
        
        
    def _removeTorrent(self, torrentIdent):
        self.log.debug('Removing from dict')
        del self.torrents[torrentIdent]
        self.log.debug('Removing from random limiter')
        self.randomSlotLimiter.removeUser(torrentIdent)
        self.log.debug('Removing from normal limiter')
        self.normalSlotLimiter.removeUser(torrentIdent)
        self.log.debug('Finished')
        
        
    ##internal functions - choking
    
    def _setSlotLimits(self, maxSlots, randomRatio):
        randomSlots = max(1, int(maxSlots * randomRatio))
        normalSlots = maxSlots - randomSlots
        self.randomSlotLimiter.changeLimit(randomSlots)
        self.normalSlotLimiter.changeLimit(normalSlots)
        
        
    def _chokeTorrent(self, torrentIdent, conns, uploadableConns, randomSlots, normalSlots, isFinished):
        shouldUpload = set()
        uploadingConns = set(conn for conn in conns if not conn.localChoked())
        
        if len(uploadableConns) == 0:
            #no conn is uploadable, nothing to do
            self.log.debug('%s - Nothing to do', torrentIdent)
        else:
            if randomSlots > 0:
                #use random slots
                randConns = sample(list(uploadableConns), randomSlots)
                for conn in randConns:
                    self.log.debug('%s - conn "%d": Picked this conn as a random upload target', torrentIdent, conn.fileno())
                    shouldUpload.add(conn)
                    uploadableConns.remove(conn)
            
            #create list for comparing the others
            if isFinished:
                compareList = [(conn.localInterested(), max(conn.getScore(), 1.0), random(), conn) for conn in uploadableConns]
            else:
                compareList = [(conn.localInterested(), conn.getScore(), 0.0, conn) for conn in uploadableConns]
            compareList.sort(reverse=True)
            
            for connSet in compareList:
                self.log.debug('%s - conn "%d": Possible Upload candidate with local Interest "%d", score "%f" and random "%f" (payload ratio "%f")',
                               torrentIdent, connSet[3].fileno(), connSet[0], connSet[1], connSet[2], connSet[3].getPayloadRatio())
            
            #get needed conns
            for connSet in compareList[:normalSlots]:
                self.log.debug('%s - conn "%d": Decided to upload to this peer', torrentIdent, connSet[3].fileno())
                shouldUpload.add(connSet[3])
                
                
            #change choke status accordingly
            unchokeConns = shouldUpload.difference(uploadingConns)
            for conn in unchokeConns:
                self.log.debug('%s - conn "%d": Unchoking', torrentIdent, conn.fileno())
                conn.setLocalChoke(False)
        
        #choke conns
        chokeConns = uploadingConns.difference(shouldUpload)
        for conn in chokeConns:
            self.log.debug('%s - conn "%d": Choking', torrentIdent, conn.fileno())
            conn.setLocalChoke(True)
        
        
    def _chokeForTorrentLimits(self):
        randomSlots = max(1, int(self.config.get('choker','maxSlots') * self.config.get('choker','randomSlotRatio')))
        normalSlots = self.config.get('choker','maxSlots') - randomSlots
        
        assert randomSlots > 0, 'No random slots?!'
        assert normalSlots > 0, 'No normal slots?!'
        
        for torrentIdent in self.torrents.iterkeys():
            gotPieces = self.torrents[torrentIdent]['ownStatus'].getGotPieces()
            isFinished = self.torrents[torrentIdent]['ownStatus'].isFinished()
            conns = self.connHandler.getAllConnections(torrentIdent)
            uploadableConns = set(conn for conn in conns if conn.remoteInterested() and conn.getStatus().hasMatchingMissingPieces(gotPieces))
            
            self._chokeTorrent(torrentIdent, conns, uploadableConns, randomSlots, normalSlots, isFinished)
        
        
    def _chokeForGlobalLimits(self):
        #get required torrent info
        torrentInfo = {}
        neededSlots = []
        for torrentIdent in self.torrents.iterkeys():
            info = {}
            gotPieces = self.torrents[torrentIdent]['ownStatus'].getGotPieces()
            info['gotPieces'] = gotPieces
            info['conns'] =  self.connHandler.getAllConnections(torrentIdent)
            info['uploadableConns'] = set(conn for conn in info['conns'] if conn.remoteInterested() and conn.getStatus().hasMatchingMissingPieces(gotPieces))
            info['neededSlots'] = len(info['uploadableConns'])
            info['isFinished'] = self.torrents[torrentIdent]['ownStatus'].isFinished()
            torrentInfo[torrentIdent] = info
            if info['neededSlots'] > 0:
                neededSlots.append((info['neededSlots'], torrentIdent))
            
        #allocate slots
        normalSlots = self.normalSlotLimiter.getQuotas(neededSlots)
        neededSlots = [(slots - normalSlots[torrentIdent], torrentIdent) for slots, torrentIdent in neededSlots]
        randomSlots = self.randomSlotLimiter.getQuotas(neededSlots)
        
        #choke
        totalRandomSlots = 0
        totalNormalSlots = 0
        for torrentIdent, info in torrentInfo.iteritems():
            self.log.info('%s - random slots %i, normal slots %i, needed slots %s', torrentIdent, randomSlots[torrentIdent], normalSlots[torrentIdent], str(info['neededSlots']))
            totalRandomSlots += randomSlots[torrentIdent]
            totalNormalSlots += normalSlots[torrentIdent]
            self._chokeTorrent(torrentIdent, info['conns'], info['uploadableConns'], randomSlots[torrentIdent], normalSlots[torrentIdent], info['isFinished'])
            
        self.log.info('Used %i/%i random slots and %i/%i normal slots', totalRandomSlots, self.randomSlotLimiter.getLimit(), totalNormalSlots, self.normalSlotLimiter.getLimit())
            
            
    ##internal functions - other
    
    def _start(self):
        if self.chokeEventId is None:
            #add event
            chokeInterval = self.config.get('choker','chokeInterval')
            self.chokeEventId = self.sched.scheduleEvent(self.choke, timedelta=chokeInterval, repeatdelta=chokeInterval)
            
            #add callback
            self.slotLimitConfigId = self.config.addCallback((('choker','maxSlots'),('choker','randomSlotRatio')) , self.changeSlotLimits,
                                                             callType='value-funcArgAll', callWithAllOptions=True)
            self.chokeIntervalConfigId = self.config.addCallback((('choker','chokeInterval'),), self.changeChokeInterval)
        
        
    def _stop(self):
        if self.chokeEventId is not None:
            #remove callbacks
            self.log.debug('Removing callbacks')
            self.config.removeCallback(self.slotLimitConfigId)
            self.config.removeCallback(self.chokeIntervalConfigId)
            
            #remove event
            self.log.debug('Removing Events')
            self.sched.removeEvent(self.chokeEventId)
            self.chokeEventId = None
            self.chokeIntervalConfigId = None
            self.slotLimitConfigId = None
            self.log.debug('Finished')
        
        
    ##external functions - choking
     
    def choke(self):
        self.lock.acquire()
        if self.chokeEventId is not None:
            self.log.info('Choking ...')
            if self.config.get('choker','slotLimitScope') == 'global':
                self._chokeForGlobalLimits()
            else:
                self._chokeForTorrentLimits()
            self.log.info('Choking finished')
        self.lock.release()
        
        
    ##external functions - torrents
    
    def addTorrent(self, torrentIdent, ownStatus):
        self.lock.acquire()
        self._addTorrent(torrentIdent, ownStatus)
        self.lock.release()
        
        
    def removeTorrent(self, torrentIdent):
        self.lock.acquire()
        self._removeTorrent(torrentIdent)
        self.lock.release()
        
        
    ##external functions - other
        
    def start(self):
        self.lock.acquire()
        self._start()
        self.lock.release()
        
        
    def stop(self):
        self.lock.acquire()
        self._stop()
        self.lock.release()
        
        
    def changeChokeInterval(self, newInterval):
        self.lock.acquire()
        if self.chokeEventId is not None:
            self.sched.changeEvent(self.chokeEventId, repeatdelta=newInterval)
            self.sched.rescheduleEvent(self.chokeEventId, timedelta=newInterval)
        self.lock.release()
        
        
    def changeSlotLimits(self, maxSlots, randomSlotRatio):
        assert type(randomSlotRatio) == float, 'Invalid type %s for randomSlotRatio!' % (str(type(randomSlotRatio)),)
        self.lock.acquire()
        self._setSlotLimits(maxSlots, randomSlotRatio)
        self.lock.release()