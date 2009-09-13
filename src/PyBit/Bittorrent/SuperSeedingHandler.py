"""
Copyright 2009  Blub

SuperSeedingHandler, a class which handles the offering of pieces when superseeding.
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

from Logger import Logger
import Messages
import threading


class SuperSeedingHandler:
    def __init__(self, ident, btPersister, ownStatus, pieceStatus):
        self.btPersister = btPersister
        self.ownStatus = ownStatus
        self.pieceStatus = pieceStatus
        self.connInfo = {}
        self.waitingConns = set()
        self.enabled = self.btPersister.get('SuperSeedingHandler-enabled', False)
        
        self.lock = threading.Lock()
        self.log = Logger('SuperSeedingHandler', '%-6s - ', ident)
                                
                                
    ##external functions - connections
    
    def addConn(self, connId, conn):
        #called when a new connection is established (before we get a bitfield from the peer)
        self.lock.acquire()
        upPieces = self.pieceStatus.getUpPieces(self.ownStatus.getGotPieces(), 2)
        assert len(upPieces) <= 2, 'Got more then we want: '+str(len(upPieces))
        self.connInfo[connId] = {'conn':conn,
                                 'upPieces':upPieces}
        if len(upPieces) == 2:
            #enough pieces to offer
            self.log.debug('Conn %-6i - Added, offering pieces %s', connId, ', '.join(str(x) for x in upPieces))
        else:
            #not enough pieces to offer
            self.log.debug('Conn %-6i - Added, offering pieces %s (adding to waiting list)', connId, ', '.join(str(x) for x in upPieces))
            self.waitingConns.add(connId)
            
        for pieceIndex in upPieces:
            conn.send(Messages.generateHave(pieceIndex))
        self.lock.release()
    
    
    def removeConn(self, connId):
        #conn got closed, need to decrease assinged uploads counter
        self.lock.acquire()
        connSet = self.connInfo[connId]
        for pieceIndex in connSet['upPieces']:
            self.pieceStatus.decreaseAssignedUploads(pieceIndex)
        self.waitingConns.discard(connId)
        del self.connInfo[connId]
        self.lock.release()
    
    
    def connGotBitfield(self, connId):
        #got a bitfield from the peer, need to check if the peer already has some of the offered pieces
        self.lock.acquire()
        connSet = self.connInfo[connId]
        connStatus = connSet['conn'].getStatus()
        
        #check for offered pieces which the peer already has
        for pieceIndex in connStatus.getMatchingGotPieces(connSet['upPieces']):
            connSet['upPieces'].remove(pieceIndex)
            self.pieceStatus.decreaseAssignedUploads(pieceIndex)
            
        #offer new pieces if needed
        if len(connSet['upPieces']) < 2:
            wantedPieces = connStatus.getMatchingMissingPieces(self.ownStatus.getGotPieces())
            wantedPieces.difference_update(connSet['upPieces'])
            pieces = self.pieceStatus.getUpPieces(wantedPieces, 2 - len(connSet['upPieces']))
            if len(pieces) == 0:
                #no piece to offer
                self.log.debug('Conn %-6i - Nothing to offer (adding to waiting list)', connId)
                self.waitingConns.add(connId)
            else:
                #offer pieces
                self.log.debug('Conn %-6i - Offering pieces %s', connId, ', '.join(str(x) for x in pieces))
                for pieceIndex in pieces:
                    connSet['upPieces'].add(pieceIndex)
                    connSet['conn'].send(Messages.generateHave(pieceIndex))
        self.lock.release()
    
    
    def connGotPiece(self, connId, pieceIndex):
        #peer got a new piece, need to offer a new one if it was one of the pieces we offered
        self.lock.acquire()
        connSet = self.connInfo[connId]
        connStatus = connSet['conn'].getStatus()
        if connStatus.isSeed():
            #does not need any pieces
            if pieceIndex in connSet['upPieces']:
                connSet['upPieces'].remove(pieceIndex)
                self.pieceStatus.decreaseAssignedUploads(pieceIndex)
                
            assert len(connSet['upPieces']) == 0, 'Does not need any pieces but we offer some?! (len: '+str(len(connSet['upPieces']))+')'
            self.log.debug('Conn %-6i - Got piece %i and does not need any other pieces (is now seed)', connId, pieceIndex)
            self.waitingConns.remove(connId)
        else:
            #needs some, so offer one more if the one obtained from it was one of the offered ones
            if not pieceIndex in connSet['upPieces']:
                #was not one of the offered pieces, nothing to do
                self.log.debug('Conn %-6i - Got piece %i which is not one of the offered pieces', connId, pieceIndex)
            else:
                #was one of the offered pieces, offer another one
                connSet['upPieces'].remove(pieceIndex)
                self.pieceStatus.decreaseAssignedUploads(pieceIndex)
                
                wantedPieces = connStatus.getMatchingMissingPieces(self.ownStatus.getGotPieces())
                wantedPieces.difference_update(connSet['upPieces'])
                upPiece = self.pieceStatus.getUpPieces(wantedPieces, 1)
                assert len(upPiece) <= 1, 'Got more then we want: '+str(len(upPiece))
                if len(upPiece) == 0:
                    #no piece to offer
                    self.log.debug('Conn %-6i - Got piece %i but nothing to offer (adding to waiting list)', connId, pieceIndex)
                    self.waitingConns.add(connId)
                else:
                    #offer piece
                    upPiece = upPiece.pop()
                    self.log.debug('Conn %-6i - Got piece %i, offering piece %i', connId, pieceIndex, upPiece)
                    connSet['upPieces'].add(upPiece)
                    connSet['conn'].send(Messages.generateHave(upPiece))
        self.lock.release()
                
                
    #external functions - general
    
    def gotNewPiece(self, pieceIndex):
        #we got a new piece - shouldn't happen during super seeding but whatever
        self.lock.acquire()
        for connId in self.waitingConns.copy():
            connSet = self.connInfo[connId]
            if not connSet['conn'].getStatus().hasPiece(pieceIndex):
                self.log.debug('Conn %-6i - Offering piece %i', connId, pieceIndex)
                connSet['upPieces'].add(pieceIndex)
                self.pieceStatus.increaseAssignedUploads(pieceIndex)
                connSet['conn'].send(Messages.generateHave(pieceIndex))
                if len(connSet['upPieces']) == 2:
                    self.waitingConns.remove(connId)
        self.lock.release()
                    
                    
    def didOfferPiece(self, connId, pieceIndex):
        self.lock.acquire()
        result = pieceIndex in self.connInfo[connId]['upPieces']
        self.lock.release()
        return result
    
    
    def getOfferedPieces(self, connId):
        self.lock.acquire()
        if self.enabled:
            result = self.connInfo[connId]['upPieces']
        else:
            result = set()
        self.lock.release()
        return result
    
    
    def hasOfferedPieces(self, connId):
        self.lock.acquire()
        if self.enabled:
            result = (len(self.connInfo[connId]['upPieces']) > 0)
        else:
            result = False
        self.lock.release()
        return result
        
    
    def isEnabled(self):
        self.lock.acquire()
        result = self.enabled
        self.lock.release()
        return result
    
    
    def setEnabled(self, enabled):
        self.lock.acquire()
        if not enabled:
            assert len(self.connInfo) == 0, 'Disabling but still conns left?!'
        self.enabled = enabled
        self.btPersister.store('SuperSeedingHandler-enabled', enabled)
        self.lock.release()