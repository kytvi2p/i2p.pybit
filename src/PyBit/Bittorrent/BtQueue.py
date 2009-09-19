"""
Copyright 2009  Blub
BtQueue, a class which represents a torrent queue (without the actual Bt-objects).
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
import logging
from collections import defaultdict
from copy import copy, deepcopy




class BtQueue:
    def __init__(self, curVersion, persister):
        self.curVersion = curVersion
        self.persister = persister
        self.log = logging.getLogger('BtQueue')
        
        self.queue = []
        self.queueInfo = {}
        self.queueSets = defaultdict(set)
        self._load()
        
        
    ##internal functions - persisting
        
    def _updatePersistedObj(self, obj):
        currentVersion = tuple((int(digit) for digit in self.curVersion.split('.')))
        objVersion = tuple((int(digit) for digit in obj['version'].split('.')))
        
        if objVersion < currentVersion:
            #need to do some updating
            if objVersion < (0,2,4):
                #pre v0.2.4 format, reconstruct everything
                self.log.info('Updating persisted obj to the v0.2.4+ format')
                newObj = {}
                oldQueue = obj['queue']
                newObj['queue'] = [ele['id'] for ele in oldQueue]
                newObj['queueInfo'] = {}
                for ele in oldQueue:
                    newObj['queueInfo'][ele['id']] = {'type':'bt',
                                                      'dataPath':ele['dataPath']}
                newObj['version'] = '0.2.4'
                obj = newObj
                objVersion = (0,2,4)
                
                #first add the new obj, then remove the old one
                self.persister.store('BtQueue-queue', obj)
                self.persister.remove('MultiBt-torrentQueue')
                
            #set current version
            obj['version'] = self.curVersion
            
            #store modified obj
            self.persister.store('BtQueue-queue', obj)
        return obj
            
        
    def _load(self):
        #try to load stored queue data
        obj = self.persister.get('BtQueue-queue')
        if obj is None:
            obj = self.persister.get('MultiBt-torrentQueue')
            
        #apply loaded data
        if obj is not None:
            obj = self._updatePersistedObj(obj)
            self.queue = obj['queue']
            self.queueInfo = obj['queueInfo']
        
        
    def _persist(self):
        persData = {'queue':self.queue,
                    'queueInfo':self.queueInfo,
                    'version':self.curVersion}
        self.persister.store('BtQueue-queue', persData)
        
    
    ##internal functions - queue
    
    def _queueGet(self):
        return self.queue
    
        
    def _queueAdd(self, queueId, queueInfo):
        self.queue.append(queueId)
        self.queueInfo[queueId] = queueInfo
        self._persist()
        
    
    def _queueContains(self, queueId):
        return (queueId in self.queue)
        
        
    def _queueMove(self, queueId, steps):
        idx = self.queue.index(queueId)
        newIdx = idx + steps
        if newIdx >= 0 and newIdx < len(self.queue):
            del self.queue[idx]
            self.queue.insert(newIdx, queueId)
            self._persist()
        
        
    def _queueRemove(self, queueId):
        self.queue.remove(queueId)
        del self.queueInfo[queueId]
        self._persist()
        
        
    def _queueNextId(self):
        if len(self.queue) == 0:
            nextId = 0
        else:
            nextId = max(self.queue) + 1
        return nextId
        
        
    ##internal functions - info
    
    def _infoGet(self, queueId):
        return self.queueInfo[queueId]
    
    
    def _infoGetKey(self, qeueId, key):
        return self.queueInfo[queueId][key]
    
    
    def _infoSet(self, queueId, info):
        self.queueInfo[queueId] = info
        self._persist()
        
        
    ##internal functions - sets
    
    def _setGet(self, key):
        return self.queueSets[key]
    
    
    def _setAdd(self, key, value):
        self.queueSets[key].add(value)
        
        
    def _setRemove(self, key, value):
        self.queueSets[key].remove(value)
        
        
    def _setContains(self, key, value):
        return (value in self.queueSets[key])
    
    
    ##external functions - torrents
    
    def queueGet(self):
        return copy(self._queueGet())
    
    
    def queueAdd(self, queueId, queueInfo):
        self._queueAdd(queueId, queueInfo)
        
    
    def queueContains(self, queueId):
        return self._queueContains(queueId)
        
        
    def queueMove(self, queueId, steps):
        self._queueMove(queueId, steps)
        
        
    def queueRemove(self, queueId):
        self._queueRemove(queueId)
        
        
    def queueNextId(self):
        return self._queueNextId()
        
        
    ##external functions - info
    
    def infoGetAll(self):
        return deepcopy(self.queueInfo)
    
    
    def infoGet(self, queueId):
        return self._infoGet(queueId).copy()
    
    
    def infoGetKey(self, queueId, key):
        return self._infoGetKey(queueId, key)
    
    
    def infoSet(self, queueId, info):
        self._infoSet(queueId, info)
        
        
    ##external functions - sets
    
    def setGet(self, key):
        return self._setGet(key).copy()
    
    
    def setAdd(self, key, value):
        self._setAdd(key, value)
        
        
    def setRemove(self, key, value):
        self._setRemove(key, value)
        
        
    def setContains(self, key, value):
        return self._setContains(key, value)
    
    
    ##external functions - stats
    
    def getStats(self, queueId):
        stats = {}
        idx = self.queue.index(queueId)
        stats['id'] = queueId
        stats['pos'] = idx + 1
        return stats