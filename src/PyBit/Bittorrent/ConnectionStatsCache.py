"""
Copyright 2010  Blub

ConnectionStatsCache, a class which caches the transfer statistics of disconnected connections.
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


from __future__ import with_statement
from collections import defaultdict, deque
import logging
import threading





class ConnectionStatsCache:
    def __init__(self):
        self.stats = {} #maps stats ids to real stats objects
        self.peerIdToStatsId = defaultdict(dict)  #maps peer ids to stats ids
        self.i2pDestToStatsId = defaultdict(dict) #maps i2p destination to stats
        
        self.nextStatsId = 0           #id for the next conn stats which get added
        self.validStatsCount = 0       #number of valid cached conn stats
        self.deprecatedStatsCount = 0  #number of old reused or "overwritten" conn stats
        self.statsQueue = deque()      #prio queue from oldest to newest cached conn stats, used to decide which one gets dropped if needed
        
        self.log = logging.getLogger('ConnectionStatsCache')
        self.lock = threading.Lock()
        
    
    ##internal functions
    
    def _checkStatsCounters(self, limit):
        #check if we exceed the cache limits
        while self.validStatsCount > limit:
            #too many valid stats
            assert len(self.statsQueue) > 0, 'many valid stats but an empty stats queue?!'
            torrentId, statsId = self.statsQueue.popleft()
            
            while statsId not in self.stats:
                #deprecated statsId, try next one
                assert len(self.statsQueue) > 0, 'many valid stats and still throwing deprecated ones away but already an empty stats queue?!'
                self.log.debug('Removed deprecated stats with id "%i" from queue', statsId)
                self.deprecatedStatsCount -= 1
                torrentId, statsId = self.statsQueue.popleft()
                
            #found a valid one, deprecate it
            self._deprecateStats(torrentId, statsId)
            self.log.debug('Removed deprecated stats with id "%i" from queue', statsId)
            self.deprecatedStatsCount -= 1 #it was already removed from the queue
            
        #check if we have too many deprecated ones
        if self.deprecatedStatsCount > limit:
            #rebuild queue, removing all deprecated ones
            self.log.debug('Rebuilding stats queue to remove all deprecated ones')
            self.statsQueue = deque(statsId for statsId in self.statsQueue if statsId in self.stats)
        
    
    def _deprecateStats(self, torrentId, statsId):
        if statsId not in self.stats:
            #nothing to do, already deprecated
            self.log.debug('Not deprecating stats with id "%i": Its already deprecated', statsId)
            
        else:
            #still around, deprecate it
            statsDict = self.stats.pop(statsId)
            del self.peerIdToStatsId[statsDict['torrentId']][statsDict['peerId']]
            del self.i2pDestToStatsId[statsDict['torrentId']][statsDict['i2pDest']]
            
            #change counters
            self.validStatsCount -= 1
            self.deprecatedStatsCount += 1
            assert self.validStatsCount >= 0, 'Less then zero valid stats?!'
            
            #log deprecation
            self.log.debug('%-6s - Deprecated stats with id "%i" (now %i valid and %i deprecated, %i torrent groups)', torrentId, statsId, self.validStatsCount, self.deprecatedStatsCount, len(self.i2pDestToStatsId))
    
    
    def _storeStats(self, torrentId, i2pDest, peerId, inRate, outRate):
        #store new conn stats
        self.log.debug('%-6s - Storing stats with id "%i"', torrentId, self.nextStatsId)
        
        #check if we already have stats stored for either the id or the i2p dest
        i2pDestStats = self.i2pDestToStatsId[torrentId].get(i2pDest, None)
        peerIdStats = self.peerIdToStatsId[torrentId].get(peerId, None)
        
        if i2pDestStats is not None:
            #we already have stats for this dest, deprecate it
            self._deprecateStats(i2pDestStats)
            
        if peerIdStats is not None:
            #we already have stats for this peer id, deprecate it
            self._deprecateStats(peerIdStats)
            
        #actually store the stats
        self.stats[self.nextStatsId] = {'torrentId':torrentId,
                                        'i2pDest':i2pDest,
                                        'peerId':peerId,
                                        'inRate':inRate,
                                        'outRate':outRate}
        self.peerIdToStatsId[torrentId][peerId] = self.nextStatsId
        self.i2pDestToStatsId[torrentId][i2pDest] = self.nextStatsId
        self.statsQueue.append((torrentId, self.nextStatsId))
        self.nextStatsId += 1
        
        #increase and then check counters
        self.validStatsCount += 1
        self._checkStatsCounters(100)
        
        
    def _getStats(self, torrentId, i2pDest, peerId):
        statsId = self.i2pDestToStatsId[torrentId].get(i2pDest, None)
        if statsId is None:
            statsId = self.peerIdToStatsId[torrentId].get(peerId, None)
            
        if statsId is None:
            #we don't have any statsIds for this i2p destination or this peer id
            self.log.debug('%-6s - Found no matching stats', torrentId)
            inRate = None
            outRate = None
            
        else:
            #found a match
            self.log.debug('%-6s - Fount matching stats with id "%i"', torrentId, statsId)
            statsDict = self.stats[statsId]
            inRate = statsDict['inRate']
            outRate = statsDict['outRate']
            self._deprecateStats(torrentId, statsId)
        
        return inRate, outRate
    
    
    ##external functions
    
    
    def get(self, torrentId, i2pDest, peerId):
        with self.lock:
            return self._getStats(torrentId, i2pDest, peerId)
    
    def store(self, torrentId, i2pDest, peerId, inRate, outRate):
        with self.lock:
            self._storeStats(torrentId, i2pDest, peerId, inRate, outRate)
            
            
    def stop(self):
        with self.lock:
            self._checkStatsCounters(0)
