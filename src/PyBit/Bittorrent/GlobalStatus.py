"""
Copyright 2009  Blub

GlobalStatus, a class for calculating how many peer have a certain piece of a torrent.
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

from collections import deque, defaultdict
from random import randrange
import logging

class GlobalStatus:
    def __init__(self, pieceAmount):
        self.pieceAmount = pieceAmount
        self.pieceAvailability = {}
        self.availabilityGroups = defaultdict(set)
        self._init()
        
        
    ##internal functions
    
    def _init(self):
        #init piece availability
        count = 0
        while count < self.pieceAmount:
            self.pieceAvailability[count] = 0
            count += 1
            
        #init availability groups
        self.availabilityGroups[0] = set(xrange(0, self.pieceAmount))
        
        
    def _increaseAvailability(self, pieces):
        #increase availability of all given pieces by one
        for pieceIndex in pieces:
            currentAvailability = self.pieceAvailability[pieceIndex]
            self.pieceAvailability[pieceIndex] += 1
            self.availabilityGroups[currentAvailability+1].add(pieceIndex)
            self.availabilityGroups[currentAvailability].remove(pieceIndex)
            if len(self.availabilityGroups[currentAvailability]) == 0:
                del self.availabilityGroups[currentAvailability]
                
                
    def _decreaseAvailability(self, pieces):
        #decrease availability of all given pieces by one
        for pieceIndex in pieces:
            currentAvailability = self.pieceAvailability[pieceIndex]
            assert currentAvailability > 0,'negative availability?!'
            self.pieceAvailability[pieceIndex] -= 1
            self.availabilityGroups[currentAvailability-1].add(pieceIndex)
            self.availabilityGroups[currentAvailability].remove(pieceIndex)
            if len(self.availabilityGroups[currentAvailability]) == 0:
                del self.availabilityGroups[currentAvailability]
        
        
    ##external functions
        
    def getPieceAmount(self):
        return len(self.pieceAvailability)
        

    def reset(self):
        self._init()


    def averageAvailability(self):
        return sum(self.pieceAvailability.itervalues())/(len(self.pieceAvailability)*1.0)


    def availableCopies(self):
        return min(self.pieceAvailability.itervalues())


    def addBitfield(self, bitfield):
        self._increaseAvailability((pieceIndex for pieceIndex in xrange(0, len(bitfield)) if bitfield[pieceIndex] == '1'))
    

    def addPiece(self, pieceIndex):
        self._increaseAvailability((pieceIndex,))


    def remBitfield(self, bitfield):
        self._decreaseAvailability((pieceIndex for pieceIndex in xrange(0, len(bitfield)) if bitfield[pieceIndex] == '1'))
            
            
    def remPiece(self, pieceIndex):
        self._decreaseAvailability(pieceIndex)
        
        
    def sortPieceList(self, *pieceSets):
        #categorise pieces
        pieceGroups = (list(self.availabilityGroups[availability].intersection(pieceSet)) for availability in sorted(self.availabilityGroups.iterkeys()) for pieceSet in pieceSets)
        return PieceIterator(pieceGroups)




class PieceIterator:
    def __init__(self, pieceGroups):
        self.pieceGroups = pieceGroups
        self.pieces = None
        self.length = 0
        
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
    
    
if __name__=='__main__':
    from time import time
    counts = (1,10,100,1000,10000,100000)
    bla = PieceIterator((range(0, count) for count in counts))
    start = time()
    y = []
    for x in bla:
        y.append(x)
    print time() - start
    #for x in y:
    #    print x
    print len(y)