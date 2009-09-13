"""
Copyright 2009  Blub

PieceStatus, a class which keeps track of all piece related information (availability, priority, ...).
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
from collections import deque, defaultdict
from random import randrange
import logging
import threading

##own
from Utilities import logTraceback


class PieceStatus:
    def __init__(self, pieceAmount):
        self.pieceAmount = pieceAmount
        
        #piece status
        self.priority = {}           #piece priority
        self.availability = {}       #piece availability
        self.concurrentRequests = {} #number of concurrent requests of the same data within a piece (minimum!), -2 = ignore
        self.finishedRequests = {}   #number of finished piece parts
        
        #groups
        self.maxConcReqs = -1                                      #highest concurrent request count
        self.concReqGroups = defaultdict(int)                      #groups of pieces which share the same concurrent request count
        self.pieceGroups = defaultdict(set)                        #groups of pieces which share the same priority, availability, concurrent requests count and finished request count (meaning the have the same overall priority)
        
        #freezing
        self.freezed = 0               #updating of self.concReqGroups and/or self.pieceGroups allowed?
        self.queuedChanges = deque()   #queued changes for self.concReqGroups and self.pieceGroups
        
        #init pieces
        self._init()
        
        #lock
        self.lock = threading.Lock()


    ##internal functions - init
        
    def _init(self):
        for pieceIndex in xrange(0, self.pieceAmount):
            self.priority[pieceIndex] = 0
            self.availability[pieceIndex] = 0
            self.concurrentRequests[pieceIndex] = 0
            self.finishedRequests[pieceIndex] = 0
        self.pieceGroups[(0,0,0,0)] = set(xrange(0, self.pieceAmount))
        self.concReqGroups[0] = self.pieceAmount


    ##internal functions - piece groups

    def _freeze(self):
        assert self.freezed == 0, 'still freezed, supported theoretically but should not happen!'
        self.freezed += 1


    def _thaw(self):
        self.freezed -= 1
        if self.freezed == 0:
            self._commitChanges()
            
            
    def _commitChanges(self):
        #commit queued changes
        for pieceIndex, oldGroupIdent, newGroupIdent in self.queuedChanges:
            if not oldGroupIdent == newGroupIdent:
                #print pieceIndex, oldGroupIdent, newGroupIdent
                #move piece index between piece groups
                self.pieceGroups[newGroupIdent].add(pieceIndex)
                self.pieceGroups[oldGroupIdent].remove(pieceIndex)
                if len(self.pieceGroups[oldGroupIdent]) == 0:
                    del self.pieceGroups[oldGroupIdent]
                    
                #update concurrent request stuff
                oldConcReqs = oldGroupIdent[2]
                newConcReqs = newGroupIdent[2]
                
                if not oldConcReqs == newConcReqs:
                    deletedOld = False
                    self.concReqGroups[newConcReqs] += 1
                    self.concReqGroups[oldConcReqs] -= 1
                    if self.concReqGroups[oldConcReqs] == 0:
                        deletedOld = True
                        del self.concReqGroups[oldConcReqs]
                
                    #update max concurrent requests
                    if newConcReqs > oldConcReqs or (deletedOld and self.maxConcReqs == oldConcReqs and newConcReqs < oldConcReqs):
                        self.maxConcReqs = newConcReqs
        
        self.queuedChanges.clear()
        
        
    def _updatePieceGroups(self, pieces, newPriority=None, availabilityChange=None, newConcurrentRequests=None,
                           newFinishedRequests=None):
        for pieceIndex in pieces:
            #create groups
            oldGroupIdent = (self.priority[pieceIndex], self.availability[pieceIndex], self.concurrentRequests[pieceIndex], self.finishedRequests[pieceIndex])
            
            if newPriority is not None:
                self.priority[pieceIndex] = newPriority
                newGroupIdent = (newPriority, self.availability[pieceIndex], self.concurrentRequests[pieceIndex], self.finishedRequests[pieceIndex])
                
            elif availabilityChange is not None:
                self.availability[pieceIndex] += availabilityChange
                newGroupIdent = (self.priority[pieceIndex], self.availability[pieceIndex], self.concurrentRequests[pieceIndex], self.finishedRequests[pieceIndex])
                
            elif newConcurrentRequests is not None:
                self.concurrentRequests[pieceIndex] = newConcurrentRequests
                newGroupIdent = (self.priority[pieceIndex], self.availability[pieceIndex], newConcurrentRequests, self.finishedRequests[pieceIndex])
                
            elif newFinishedRequests is not None:
                self.finishedRequests[pieceIndex] = newFinishedRequests
                newGroupIdent = (self.priority[pieceIndex], self.availability[pieceIndex], self.concurrentRequests[pieceIndex], newFinishedRequests)
            
            #update state if possible
            if self.freezed:
                #not allowed to do the change right now
                self.queuedChanges.append((pieceIndex, oldGroupIdent, newGroupIdent))
            else:
                #allowed
                if not oldGroupIdent == newGroupIdent:
                    #print pieceIndex, oldGroupIdent, newGroupIdent
                    #move piece index between piece groups
                    self.pieceGroups[newGroupIdent].add(pieceIndex)
                    self.pieceGroups[oldGroupIdent].remove(pieceIndex)
                    if len(self.pieceGroups[oldGroupIdent]) == 0:
                        del self.pieceGroups[oldGroupIdent]
                        
                    #update concurrent request stuff
                    oldConcReqs = oldGroupIdent[2]
                    newConcReqs = newGroupIdent[2]
                    
                    if not oldConcReqs == newConcReqs:
                        deletedOld = False
                        self.concReqGroups[newConcReqs] += 1
                        self.concReqGroups[oldConcReqs] -= 1
                        if self.concReqGroups[oldConcReqs] == 0:
                            deletedOld = True
                            del self.concReqGroups[oldConcReqs]
                    
                        #update max concurrent requests
                        if newConcReqs > oldConcReqs or (deletedOld and self.maxConcReqs == oldConcReqs and newConcReqs < oldConcReqs):
                            self.maxConcReqs = newConcReqs


    ##external functions - status

    def increaseAvailability(self, pieceIndex=None, bitfield=None):
        self.lock.acquire()
        if pieceIndex is not None:
            self._updatePieceGroups((pieceIndex,), availabilityChange=1)
        if bitfield is not None:
            self._updatePieceGroups((pieceIndex for pieceIndex in xrange(0, len(bitfield)) if bitfield[pieceIndex] == '1'), availabilityChange=1)
        self.lock.release()


    def decreaseAvailability(self, pieceIndex=None, bitfield=None):
        self.lock.acquire()
        if pieceIndex is not None:
            self._updatePieceGroup((pieceIndex,), availabilityChange=-1)
        if bitfield is not None:
            self._updatePieceGroups((pieceIndex for pieceIndex in xrange(0, len(bitfield)) if bitfield[pieceIndex] == '1'), availabilityChange=-1)
        self.lock.release()


    def getPriority(self, pieceIndex=None, pieces=None):
        self.lock.acquire()
        if pieceIndex is None:
            priority = self.priority[pieceIndex] * -1
        else:
            priority = {}
            for pieceIndex in pieces:
                priority[pieceIndex] = self.priority[pieceIndex] * -1
        self.lock.release()
        return priority


    def setPriority(self, pieces, newPriority):
        self.lock.acquire()
        self._updatePieceGroups((pieceIndex for pieceIndex in pieces if not self.priority[pieceIndex] == newPriority) , newPriority=newPriority)
        self.lock.release()


    def setConcurrentRequestsCounter(self, pieces, newConcurrentRequests):
        self.lock.acquire()
        if newConcurrentRequests == 0:
            newConcurrentRequests = -1
        elif newConcurrentRequests == -1:
            newConcurrentRequests = 0
            
        self._updatePieceGroups((pieceIndex for pieceIndex in pieces if not self.concurrentRequests[pieceIndex] == newConcurrentRequests), newConcurrentRequests=newConcurrentRequests)
        self.lock.release()


    def setFinishedRequestsCounter(self, pieces, newFinishedRequests):
        self.lock.acquire()
        newFinishedRequests *= -1
        self._updatePieceGroups((pieceIndex for pieceIndex in pieces if not self.finishedRequests[pieceIndex] == newFinishedRequests), newFinishedRequests=newFinishedRequests)
        self.lock.release()


    ##external functions - info

    def getPieceAmount(self):
        self.lock.acquire()
        length = self.pieceAmount
        self.lock.release()
        return length
    
    
    def getMaxConcReqs(self):
        self.lock.acquire()
        result = self.maxConcReqs
        self.lock.release()
        return result
    
    
    def inEndgame(self):
        self.lock.acquire()
        assert not self.freezed, 'cannot be accurate during freeze!'
        if self.concReqGroups[0] == 0 and self.concReqGroups[-1] == 0:
            result = True
        else:
            result = False
        self.lock.release()
        return result


    ##external functions - requesting

    def thaw(self):
        self.lock.acquire()
        self._thaw()
        self.lock.release()
        

    def sortPieceList(self, pieces, *concReqCounts):
        self.lock.acquire()
        self._freeze()
        
        allowedConcReqCounts = set()
        for count in concReqCounts:
            if count == 0:
                count = -1
            elif count == -1:
                count = 0
            allowedConcReqCounts.add(count)

        pieceGroups = (list(self.pieceGroups[groupIdent].intersection(pieces)) for groupIdent in sorted(groupId for groupId in self.pieceGroups.iterkeys() if (not groupId[1] == 0) and groupId[2] in allowedConcReqCounts))
        iterator = PieceIterator(self.thaw, pieceGroups)
        self.lock.release()
        return iterator




class PieceIterator:
    def __init__(self, finishIterFunc, pieceGroups):
        self.finishIterFunc = finishIterFunc
        self.pieceGroups = pieceGroups
        self.pieces = None
        self.length = 0

    def __del__(self):
        try:
            self.finishIterFunc()
        except:
            log = logging.getLogger('PieceIterator')
            log.error('Error in __del__:\n%s', logTraceback())
        
    def __iter__(self):
        return self
    
    def next(self):
        while self.length == 0:
            #refill
            self.pieces = self.pieceGroups.next()
            self.length = len(self.pieces)
            
        if self.length == 1:
            #no need for randomising
            pieceIndex = self.pieces[0]
            self.pieces = None
            self.length = 0
        else:
            #random choice
            idx = randrange(0, self.length)
            pieceIndex = self.pieces[idx]
            if idx < self.length - 1:
                self.pieces[idx] = self.pieces.pop()
            else:
                del self.pieces[idx]
            self.length -= 1
            
        return pieceIndex
