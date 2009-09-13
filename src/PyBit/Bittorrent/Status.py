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

from Conversion import binaryToBin, binToBinary

class Status:
    def __init__(self, pieceAmount, pieceStatus=None):
        self.pieceAmount = pieceAmount
        self.pieceStatus = pieceStatus
        
        self._initStatus()
        
        self.lock = threading.RLock()
        
        
    ##internal functions - bitfield
    
    def _getBitfield(self):
        return ''.join((str(int(pieceIndex in self.gotPieces)) for pieceIndex in xrange(0, self.pieceAmount)))
        
        
    ##internal functions - pieces
        
    def _initStatus(self):
        self.gotPieces = set()
        self.gotPiecesCount = 0
        self.missingPieces = set()
        
        for piece in xrange(0, self.pieceAmount):
            self.missingPieces.add(piece)
        self.missingPiecesCount = self.pieceAmount
        
        
    def _clear(self):
        if self.pieceStatus is not None:
            self.pieceStatus.decreaseAvailability(bitfield=self._getBitfield())
        self._initStatus()
            
            
    def _addBitfield(self, bitfield):
        for pieceIndex in xrange(0, self.pieceAmount):
            if bitfield[pieceIndex]=='1':
                self.gotPieces.add(pieceIndex)
                self.missingPieces.remove(pieceIndex)
                self.gotPiecesCount += 1
                self.missingPiecesCount -=1
                
        if self.pieceStatus is not None:
            self.pieceStatus.increaseAvailability(bitfield=bitfield)
    
    
    def _gotPiece(self, pieceIndex):
        self.missingPieces.remove(pieceIndex)
        self.gotPieces.add(pieceIndex)
        self.gotPiecesCount += 1
        self.missingPiecesCount -= 1
        
        if self.pieceStatus is not None:
            self.pieceStatus.increaseAvailability(pieceIndex=pieceIndex)
    
    
    def _setPieceStatus(self, pieceIndex, got):
        if got and pieceIndex in self.missingPieces:
            #piece is in wrong set
            self.missingPieces.remove(pieceIndex)
            self.gotPieces.add(pieceIndex)
            self.missingPiecesCount -= 1
            self.gotPiecesCount += 1
            if self.pieceStatus is not None:
                self.pieceStatus.increaseAvailability(pieceIndex=pieceIndex)
        
        elif (not got) and pieceIndex in self.gotPieces:
            #piece is in wrong set
            self.gotPieces.remove(pieceIndex)
            self.missingPieces.add(pieceIndex)
            self.gotPiecesCount -= 1
            self.missingPiecesCount += 1
            if self.pieceStatus is not None:
                self.pieceStatus.decreaseAvailability(pieceIndex=pieceIndex)
        
    
    ##external functions - change status
    
    def addBitfield(self, bitfield):
        self.lock.acquire()
        self._addBitfield(bitfield)
        self.lock.release()


    def gotPiece(self, pieceIndex):
        self.lock.acquire()
        assert pieceIndex in self.missingPieces,'got piece which we already had?!'
        self._gotPiece(pieceIndex)
        self.lock.release()
        
        
    def setPieceStatus(self, pieceIndex, got):
        self.lock.acquire()
        self._setPieceStatus(pieceIndex, got)
        self.lock.release()
        
        
    def clear(self):
        self.lock.acquire()
        self._clear()
        self.lock.release()
        
        
    ##external functions - get information about the pieces
    
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
    
    
    ##external functions - other
    
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




class OwnStatus(Status):
    def __init__(self, pieceAmount, pieceStatus=None):
        Status.__init__(self, pieceAmount, pieceStatus)
        
    ##internal functions - pieces
        
    def _initStatus(self):
        Status._initStatus(self)
        self.wantedPieces = set(xrange(0, self.pieceAmount)) #pieces which we actually want to download
        self.wantedPiecesCount = self.pieceAmount
        self.neededPieces = self.missingPieces.copy()        #pieces which are both missing and wanted
        self.neededPiecesCount = self.missingPiecesCount
            
            
    def _addBitfield(self, bitfield):
        for pieceIndex in xrange(0, self.pieceAmount):
            if bitfield[pieceIndex]=='1':
                if pieceIndex in self.neededPieces:
                    self.neededPieces.remove(pieceIndex)
                    self.neededPiecesCount -= 1
        Status._addBitfield(self, bitfield)
    
    
    def _gotPiece(self, pieceIndex):
        assert pieceIndex in self.neededPieces, 'got piece which we don\'t want?!'
        self.neededPieces.remove(pieceIndex)
        self.neededPiecesCount -= 1
        Status._gotPiece(self, pieceIndex)
    
    
    def _setPieceStatus(self, pieceIndex, got):
        if got and pieceIndex in self.neededPieces:
            #piece is no longer needed
            self.neededPieces.remove(pieceIndex)
            self.neededPiecesCount -= 1
            
        elif (not got) and (not pieceIndex in self.neededPieces) and pieceIndex in self.wantedPieces:
            #piece is again needed
            self.neededPieces.add(pieceIndex)
            self.neededPiecesCount += 1
            
        Status._setPieceStatus(self, pieceIndex, got)
        
        
    def _setPieceWantedFlag(self, pieces, wanted):
        for pieceIndex in pieces:
            if wanted and pieceIndex not in self.wantedPieces:
                self.wantedPieces.add(pieceIndex)
                self.wantedPiecesCount += 1
                if pieceIndex in self.missingPieces:
                    self.neededPieces.add(pieceIndex)
                    self.neededPiecesCount += 1
                    
            elif (not wanted) and pieceIndex in self.wantedPieces:
                self.wantedPieces.remove(pieceIndex)
                self.wantedPiecesCount -= 1
                if pieceIndex in self.missingPieces:
                    self.neededPieces.remove(pieceIndex)
                    self.neededPiecesCount -= 1
    
    
    ##external functions - change status
        
    def setPieceWantedFlag(self, pieces, wanted):
        self.lock.acquire()
        self._setPieceWantedFlag(pieces, wanted)
        self.lock.release()
        
        
    ##external functions - get information about the pieces
    
    def getWantedPieces(self):
        self.lock.acquire()
        pieces = self.wantedPieces.copy()
        self.lock.release()
        return pieces
    
    
    def getNeededPieces(self):
        self.lock.acquire()
        pieces = self.neededPieces.copy()
        self.lock.release()
        return pieces
    
    
    def getAmountOfWantedPieces(self):
        self.lock.acquire()
        count = self.wantedPiecesCount
        self.lock.release()
        return count
    
    
    def getAmountOfNeededPieces(self):
        self.lock.acquire()
        count = self.neededPiecesCount
        self.lock.release()
        return count
    
    
    def hasMatchingWantedPieces(self, pieces):
        self.lock.acquire()
        result = (len(self.wantedPieces.intersection(pieces)) > 0)
        self.lock.release()
        return result
    
    
    def hasMatchingNeededPieces(self, pieces):
        self.lock.acquire()
        result = (len(self.neededPieces.intersection(pieces)) > 0)
        self.lock.release()
        return result
    
    
    def getMatchingWantedPieces(self, pieces):
        self.lock.acquire()
        pieces = self.wantedPieces.intersection(pieces)
        self.lock.release()
        return pieces
    
    
    def getMatchingNeededPieces(self, pieces):
        self.lock.acquire()
        pieces = self.neededPieces.intersection(pieces)
        self.lock.release()
        return pieces
    
    
    def wantsPiece(self, pieceIndex):
        self.lock.acquire()
        result = pieceIndex in self.wantedPieces
        self.lock.release()
        return result
    
    
    def needsPiece(self, pieceIndex):
        self.lock.acquire()
        result = pieceIndex in self.neededPieces
        self.lock.release()
        return result
    
    
    ##external functions - other
    
    def isFinished(self):
        self.lock.acquire()
        result = self.neededPiecesCount == 0
        self.lock.release()
        return result
    
    
    
    
class PersistentOwnStatus(OwnStatus):
    def __init__(self, btPersister, shouldPersist, pieceAmount, pieceStatus=None):
        self.btPersister = btPersister
        self.shouldPersist = shouldPersist
        self.allowedToPersist = False
        if not self.shouldPersist:
            #remove any leftovers
            self.btPersister.remove('PersistentStatus-bitfield')
            
        OwnStatus.__init__(self, pieceAmount, pieceStatus)
        
        
    ##internal functions - persisting
        
    def _persist(self):
        if self.shouldPersist and self.allowedToPersist:
            binaryBitfield = binToBinary(''.join((str(int(pieceIndex in self.gotPieces)) for pieceIndex in xrange(0, self.pieceAmount))))
            self.btPersister.store('PersistentStatus-bitfield', binaryBitfield)
                
        
    ##internal functions - pieces
        
    def _clear(self):
        OwnStatus._clear(self)
        self._persist()
            
            
    def _addBitfield(self, bitfield):
        OwnStatus._addBitfield(self, bitfield)
        self._persist()
    
    
    def _gotPiece(self, pieceIndex):
        OwnStatus._gotPiece(self, pieceIndex)
        self._persist()
            
    
    def _setPieceStatus(self, pieceIndex, got):
        OwnStatus._setPieceStatus(self, pieceIndex, got)
        self._persist()
                
                
    ##external functions - persisting
    
    def loadPersistedData(self):
        self.lock.acquire()
        success = False
        if self.shouldPersist:
            bitfield = self.btPersister.get('PersistentStatus-bitfield', None)
            if bitfield is not None:
                success = True
                self._addBitfield(binaryToBin(bitfield))
        self.lock.release()
        return success
    
    
    def persist(self):
        #called once the initial loading is done, from here on automatic persists are also allowed
        self.lock.acquire()
        self.allowedToPersist = True
        self._persist()
        self.lock.release()
    
    
    def enablePersisting(self, active):
        self.lock.acquire()
        if active and (not self.shouldPersist):
            #got activated
            self.shouldPersist = True
            self._persist()
            
        elif (not active) and self.shouldPersist:
            #got deactived
            self.shouldPersist = False
            self.btPersister.remove('PersistentStatus-bitfield')
            
        self.lock.release()