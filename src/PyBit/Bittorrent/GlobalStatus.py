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

from random import choice

class GlobalStatus:
    def __init__(self, pieceAmount):
        self.statusCount = 0
        self.pieces = {}
        count = 0
        while count < pieceAmount:
            self.pieces[count] = 0
            count += 1
            
    def getPieceAmount(self):
        return len(self.pieces)

    def increaseStatusCount(self):
        self.statusCount += 1
        
        
    def decreaseStatusCount(self):
        self.statusCount -= 1
        

    def reset(self):
        for pieceIndex in self.pieces.iterkeys():
            self.pieces[pieceIndex]=0


    def averageAvailability(self):
        return sum(self.pieces.itervalues())/(len(self.pieces)*1.0)


    def availableCopies(self):
        return min(self.pieces.itervalues())


    def addBitfield(self, bitfield):
        for pieceIndex in xrange(0, len(bitfield)):
            if bitfield[pieceIndex]=='1':
                self.pieces[pieceIndex] += 1
    

    def addPiece(self, pieceIndex):
        self.pieces[pieceIndex] += 1


    def remBitfield(self, bitfield):
        for pieceIndex in xrange(0, len(bitfield)):
            if bitfield[pieceIndex]=='1':
                self.pieces[pieceIndex] -= 1
            
            
    def remPiece(self, pieceIndex):
        self.pieces[pieceIndex] -= 1
        

    def getRarest(self, pieces):
        number = None
        
        for pieceIndex in pieces:
            newNumber = self.pieces[pieceIndex]
            if number is None:
                pieceIndexs = [pieceIndex]
                number = newNumber
            else:
                if newNumber < number:
                    pieceIndexs = [pieceIndex]
                    number = newNumber
                    
                elif newNumber == number:
                    pieceIndexs.append(pieceIndex)
                
        if len(pieceIndexs) > 1:
            return choice(pieceIndexs)
        else:
            return pieceIndexs[0]
            
