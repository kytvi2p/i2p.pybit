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
        
        #piece status - requests
        self.priority = {}           #piece priority
        self.availability = {}       #piece availability
        self.concurrentRequests = {} #number of concurrent requests of the same data within a piece (minimum!), -2 = ignore
        self.finishedRequests = {}   #number of finished piece parts
        
        #piece status - uploads
        self.assignedUploads = {}    #assigned uploads (=pieces available to peers who need them, super seeding)
        
        #groups - requests
        self.maxConcReqs = -1                                      #highest concurrent request count
        self.concReqGroups = defaultdict(int)                      #groups of pieces which share the same concurrent request count
        self.pieceGroups = defaultdict(set)                        #groups of pieces which share the same priority, availability, concurrent requests count and finished request count (meaning the have the same overall priority)
        
        #groups - uploads
        self.upPieceGroups = defaultdict(set)
        
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
            self.assignedUploads[pieceIndex] = 0
        self.pieceGroups[(0,0,0,0)] = set(xrange(0, self.pieceAmount))
        self.concReqGroups[0] = self.pieceAmount
        self.upPieceGroups[0] = set(xrange(0, self.pieceAmount))


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
        for pieceIndex, oldReqGroupIdent, newReqGroupIdent, oldUpGroupIdent, newUpGroupIdent in self.queuedChanges:
            if not oldReqGroupIdent == newReqGroupIdent:
                #print pieceIndex, oldReqGroupIdent, newReqGroupIdent
                #move piece index between piece groups
                self.pieceGroups[newReqGroupIdent].add(pieceIndex)
                self.pieceGroups[oldReqGroupIdent].remove(pieceIndex)
                if len(self.pieceGroups[oldReqGroupIdent]) == 0:
                    del self.pieceGroups[oldReqGroupIdent]
                    
                #update concurrent request stuff
                oldConcReqs = oldReqGroupIdent[2]
                newConcReqs = newReqGroupIdent[2]
                
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
                        
                        
            if not oldUpGroupIdent == newUpGroupIdent:
                #print pieceIndex, oldUpGroupIdent, newUpGroupIdent
                #move piece index between piece groups
                self.upPieceGroups[newUpGroupIdent].add(pieceIndex)
                self.upPieceGroups[oldUpGroupIdent].remove(pieceIndex)
                if len(self.upPieceGroups[oldUpGroupIdent]) == 0:
                    del self.upPieceGroups[oldUpGroupIdent]
        
        self.queuedChanges.clear()
        
        
    def _updatePieceGroups(self, pieces, newPriority=None, availabilityChange=None, newConcurrentRequests=None,
                           newFinishedRequests=None, assignedUploadsChange=None):
        for pieceIndex in pieces:
            #create groups
            priority = self.priority[pieceIndex]
            availability = self.availability[pieceIndex]
            concurrentRequests = self.concurrentRequests[pieceIndex]
            finishedRequests = self.finishedRequests[pieceIndex]
            assignedUploads = self.assignedUploads[pieceIndex]
            
            #remember old groups
            oldReqGroupIdent = (priority, availability, concurrentRequests, finishedRequests)
            oldUpGroupIdent = availability + assignedUploads
            
            #make changes
            if newPriority is not None:
                self.priority[pieceIndex] = newPriority
                priority = newPriority
                
            elif availabilityChange is not None:
                self.availability[pieceIndex] += availabilityChange
                availability += availabilityChange
                
            elif newConcurrentRequests is not None:
                self.concurrentRequests[pieceIndex] = newConcurrentRequests
                concurrentRequests = newConcurrentRequests
                
            elif newFinishedRequests is not None:
                self.finishedRequests[pieceIndex] = newFinishedRequests
                finishedRequests = newFinishedRequests
                
            elif assignedUploadsChange is not None:
                self.assignedUploads[pieceIndex] += assignedUploadsChange
                assignedUploads += assignedUploadsChange
            
            #build new groups
            newReqGroupIdent = (priority, availability, concurrentRequests, finishedRequests)
            newUpGroupIdent = availability + assignedUploads
            
            #update state if possible
            if self.freezed:
                #not allowed to do the change right now
                self.queuedChanges.append((pieceIndex, oldReqGroupIdent, newReqGroupIdent, oldUpGroupIdent, newUpGroupIdent))
            else:
                #allowed
                if not oldReqGroupIdent == newReqGroupIdent:
                    #print pieceIndex, oldReqGroupIdent, newReqGroupIdent
                    #move piece index between piece groups
                    self.pieceGroups[newReqGroupIdent].add(pieceIndex)
                    self.pieceGroups[oldReqGroupIdent].remove(pieceIndex)
                    if len(self.pieceGroups[oldReqGroupIdent]) == 0:
                        del self.pieceGroups[oldReqGroupIdent]
                        
                    #update concurrent request stuff
                    oldConcReqs = oldReqGroupIdent[2]
                    newConcReqs = newReqGroupIdent[2]
                    
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
                            
                if not oldUpGroupIdent == newUpGroupIdent:
                    #print pieceIndex, oldUpGroupIdent, newUpGroupIdent
                    #move piece index between piece groups
                    self.upPieceGroups[newUpGroupIdent].add(pieceIndex)
                    self.upPieceGroups[oldUpGroupIdent].remove(pieceIndex)
                    if len(self.upPieceGroups[oldUpGroupIdent]) == 0:
                        del self.upPieceGroups[oldUpGroupIdent]


    ##external functions - status
    
    def getAvailability(self, pieceIndex=None, pieces=None):
        self.lock.acquire()
        if pieceIndex is not None:
            availability = self.availability[pieceIndex]
        else:
            availability = {}
            for pieceIndex in pieces:
                availability[pieceIndex] = self.availability[pieceIndex]
        self.lock.release()
        return availability

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
        if pieceIndex is not None:
            priority = self.priority[pieceIndex] * -1
        else:
            priority = {}
            for pieceIndex in pieces:
                priority[pieceIndex] = self.priority[pieceIndex] * -1
        self.lock.release()
        return priority


    def setPriority(self, pieces, newPriority):
        self.lock.acquire()
        newPriority *= -1
        self._updatePieceGroups((pieceIndex for pieceIndex in pieces if not self.priority[pieceIndex] == newPriority) , newPriority=newPriority)
        self.lock.release()
        
        
    def getConcurrentRequestsCounter(self, pieceIndex):
        self.lock.acquire()
        concRequests = self.concurrentRequests[pieceIndex]
        if concRequests == -1:
            concRequests = 0
        elif concRequests == 0:
            concRequests = -1
        self.lock.release()
        return concRequests


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
        
    def getAssignedUploads(self, pieceIndex):
        self.lock.acquire()
        assignedUploads = self.assignedUploads[pieceIndex]
        self.lock.release()
        return assignedUploads
        
    def increaseAssignedUploads(self, pieceIndex):
        self.lock.acquire()
        self._updatePieceGroups((pieceIndex,), assignedUploadsChange=1)
        self.lock.release()


    def decreaseAssignedUploads(self, pieceIndex):
        self.lock.acquire()
        self._updatePieceGroups((pieceIndex,), assignedUploadsChange=-1)
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
    
    
    ##external functions - uploading
    
    def getUpPieces(self, possiblePieces, count):
        self.lock.acquire()
        pieceGroups = (list(self.upPieceGroups[groupIdent].intersection(possiblePieces)) for groupIdent in sorted(self.upPieceGroups.iterkeys()))
        iterator = PieceIterator(None, pieceGroups)
        upPieces = []
        for piece in iterator:
            upPieces.append(piece)
            if len(upPieces) == count:
                break
        self._updatePieceGroups(upPieces, assignedUploadsChange=1)
        self.lock.release()
        return set(upPieces)
    
    
    ##external functions - stats
    
    def getStats(self, **kwargs):
        self.lock.acquire()
        stats = {}
        if kwargs.get('pieceAverages', False):
            stats['avgPieceAvailability'] = (sum(self.availability.itervalues()) * 1.0) / max(len(self.availability), 1)
            stats['minPieceAvailability'] = min(self.availability.itervalues())
        self.lock.release()
        return stats




class PieceIterator:
    def __init__(self, finishIterFunc, pieceGroups):
        self.finishIterFunc = finishIterFunc
        self.pieceGroups = pieceGroups
        self.pieces = None
        self.length = 0

    def __del__(self):
        try:
            if self.finishIterFunc is not None:
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
