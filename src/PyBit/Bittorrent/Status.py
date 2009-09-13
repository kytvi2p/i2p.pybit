"""
Copyright 2009  Blub

Status, a class which keeps track of which piece a peer has and which it is missing.
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
import threading

class Status:
    def __init__(self, pieceAmount, globalStatus=None):
        self.pieceAmount = pieceAmount
        self.globalStatus = globalStatus
        
        self._initStatus()
        
        self.lock = threading.RLock()
        
        
    def _initStatus(self):
        self.gotPieces = set()
        self.gotPiecesCount = 0
        self.missingPieces = set()
        
        for piece in xrange(0, self.pieceAmount):
            self.missingPieces.add(piece)
        self.missingPiecesCount = self.pieceAmount
        
        
    def _getBitfield(self):
        bitfield = deque()
        pieceIndex = 0
        while pieceIndex < self.gotPiecesCount + self.missingPiecesCount:
            if pieceIndex in self.gotPieces:
                bitfield.append('1')
            else:
                bitfield.append('0')
            pieceIndex += 1
        bitfield = ''.join(bitfield)
        return bitfield
        
    
    ##functions to change status
    
    def addBitfield(self, bitfield):
        self.lock.acquire()
        for pieceIndex in xrange(0, len(bitfield)):
            if bitfield[pieceIndex]=='1':
                self.gotPieces.add(pieceIndex)
                self.missingPieces.remove(pieceIndex)
                self.gotPiecesCount += 1
                self.missingPiecesCount -=1
                
        if self.globalStatus is not None:
            self.globalStatus.addBitfield(bitfield)
        self.lock.release()


    def gotPiece(self, pieceIndex):
        self.lock.acquire()
        assert pieceIndex in self.missingPieces,'got piece which we already had?!'
        
        self.missingPieces.remove(pieceIndex)
        self.gotPieces.add(pieceIndex)
        self.gotPiecesCount += 1
        self.missingPiecesCount -= 1
        
        if self.globalStatus is not None:
            self.globalStatus.addPiece(pieceIndex)            
        self.lock.release()
        
        
    ##functions to get information about the pieces
    
    def getGotPieces(self):
        self.lock.acquire()
        pieces = self.gotPieces.copy()
        self.lock.release()
        return pieces
    

    def getMissingPieces(self):
        self.lock.acquire()
        pieces = self.missingPieces.copy()
        self.lock.release()
        return pieces
    
    
    def getAmountOfGotPieces(self):
        self.lock.acquire()
        count = self.gotPiecesCount
        self.lock.release()
        return count
    

    def getAmountOfMissingPieces(self):
        self.lock.acquire()
        count = self.missingPiecesCount
        self.lock.release()
        return count
    

    def hasMatchingGotPieces(self, pieces):
        self.lock.acquire()
        result = (len(self.gotPieces.intersection(pieces)) > 0)
        self.lock.release()
        return result
    

    def hasMatchingMissingPieces(self, pieces):
        self.lock.acquire()
        result = (len(self.missingPieces.intersection(pieces)) > 0)
        self.lock.release()
        return result
    

    def getMatchingGotPieces(self, pieces):
        self.lock.acquire()
        pieces = self.gotPieces.intersection(pieces)
        self.lock.release()
        return pieces


    def getMatchingMissingPieces(self, pieces):
        self.lock.acquire()
        pieces = self.missingPieces.intersection(pieces)
        self.lock.release()
        return pieces
    

    def getBitfield(self):
        self.lock.acquire()
        bitfield = self._getBitfield()
        self.lock.release()
        return bitfield
    
    
    def hasPiece(self, pieceIndex):
        self.lock.acquire()
        result = pieceIndex in self.gotPieces
        self.lock.release()
        return result
    

    def needsPiece(self, pieceIndex):
        self.lock.acquire()
        result =  pieceIndex in self.missingPieces
        self.lock.release()
        return result
    
    
    def getAmountOfPieces(self):
        self.lock.acquire()
        count = self.pieceAmount
        self.lock.release()
        return count
    
    
    ##other
    
    def clear(self):
        self.lock.acquire()
        if self.globalStatus is not None:
            self.globalStatus.remBitfield(self._getBitfield())
        self._initStatus()
        self.lock.release()
        
    
    def getPercent(self):
        self.lock.acquire()
        percent = 100*(self.gotPiecesCount/((self.gotPiecesCount+self.missingPiecesCount)*1.0))
        self.lock.release()
        return percent
    

    def isSeed(self):
        self.lock.acquire()
        result = self.missingPiecesCount==0
        self.lock.release()
        return result
