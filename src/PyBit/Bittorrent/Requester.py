"""
Copyright 2009  Blub

Requester, a class which makes requests to other peers.
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
from sha import sha

from Logger import Logger
from Request import Request
from Utilities import logTraceback


class Requester:
    def __init__(self, config, ident, pieceStatus, storage, torrent):
        self.config = config
        self.storage = storage
        self.torrent = torrent
        self.pieceStatus = pieceStatus
        self.ownStatus = storage.getStatus()
        
        self.requestedPieces = {} #pieces which are (partly) requested
        self.waitingConns = set() #connections which allow requests and are not filled
        
        self.log = Logger('Requester', '%-6s - ', ident)
    
    
    ##internal functions - requesting
    
    def _makeRequestsForPieces(self, conn, neededRequests, pieces, endgame):
        assert neededRequests > 0,'requesting 0 requests?!'
        
        for pieceIndex in pieces:
            #iterate over pieces until we added enough requests
            if not pieceIndex in self.requestedPieces:
                #first request for this piece
                assert not endgame,'Endgame but still pieces left?!'
                requestObj = Request(self.pieceStatus, pieceIndex, self.torrent.getLengthOfPiece(pieceIndex), 4096)
                self.requestedPieces[pieceIndex] = requestObj
                requests = requestObj.getRequests(neededRequests, conn)
                assert len(requests) > 0,str(pieceIndex)+': new request but nothing requestable?!'
                
            else:
                #a request obj exists
                requestObj = self.requestedPieces[pieceIndex]
                excludeRequests = conn.getInRequestsOfPiece(pieceIndex)
                requests = requestObj.getRequests(neededRequests, conn, excludeRequests, endgame)

            if len(requests) > 0:
                #got some valid requests
                for request in requests:
                    #add request
                    self.log.info('Conn %i: Requesting piece %i, offset %i, length %i', conn.fileno(), pieceIndex, request[0], request[1])
                    conn.addInRequest(pieceIndex, request[0], request[1],
                                      failFunc=self.failedRequest,
                                      failFuncArgs=[conn, pieceIndex, request[0], request[1]])
                    neededRequests -= 1
                    
                if neededRequests == 0:
                    #finished
                    break
                    
        return neededRequests
                
                
    def _makeRequestsForConn(self, conn):
        #try to fill conn with requests
        neededRequests = conn.getMaxAmountOfInRequests() - conn.getAmountOfInRequests()
        if neededRequests < 0:
            #bug!
            self.log.warn('Conn %i: Already %i requests queued but the max is %i!', conn.fileno(), conn.getAmountOfInRequests(), conn.getMaxAmountOfInRequests())
            
        elif neededRequests == 0:
            #already filled
            self.log.info('Conn %i: Already filled with requests, nothing to do', conn.fileno())
            
        else:
            #actually need to request something
            allRequestablePieces = conn.getStatus().getGotPieces()
            
            #self.log.debug('available pieces:\n%s', str(sorted(connStatus.getGotPieces())))
            #self.log.debug('needed pieces:\n%s', str(sorted(self.requestablePieces[-1])))
            #self.log.debug('in-progress pieces:\n%s', str(sorted(self.requestablePieces[0])))
            
            if not self.config.getBool('requester','strictAvailabilityPrio'):
                #first try in progress pieces
                requestablePieces = self.pieceStatus.sortPieceList(allRequestablePieces, 0)                  #sort them by availability (rarer pieces first)
                neededRequests = self._makeRequestsForPieces(conn, neededRequests, requestablePieces, False) #make requests
                del requestablePieces
                
                if neededRequests > 0:
                    #now try unrequested pieces
                    requestablePieces = self.pieceStatus.sortPieceList(allRequestablePieces, -1)                 #sort them by availability (rarer pieces first)
                    neededRequests = self._makeRequestsForPieces(conn, neededRequests, requestablePieces, False) #make requests
                    del requestablePieces
                    
            else:
                #try both at once
                requestablePieces = self.pieceStatus.sortPieceList(allRequestablePieces, 0, -1)              #sort them by availability (rarer pieces first)
                neededRequests = self._makeRequestsForPieces(conn, neededRequests, requestablePieces, False) #make requests
                del requestablePieces
                
            if neededRequests > 0 and self.pieceStatus.inEndgame():
                #still need to do more requests and we are in endgame mode
                idx = 1
                while neededRequests > 0 and idx <= self.pieceStatus.getMaxConcReqs():
                    requestablePieces = self.pieceStatus.sortPieceList(allRequestablePieces, idx)               #sort them by availability (rarer pieces first)
                    neededRequests = self._makeRequestsForPieces(conn, neededRequests, requestablePieces, True) #make requests
                    del requestablePieces
                    idx += 1
                    
            if neededRequests > 0:
                #couldn't get enough requests
                self.waitingConns.add(conn)
            else:
                #conn is filled
                self.waitingConns.discard(conn)
    
    
    def _tryPieceWithWaitingConns(self, pieceIndex):
        #called if a whole piece failed, checks if some of the waiting conns may process this piece
        for conn in self.waitingConns.copy():
            #try one conn
            if conn.getStatus().hasPiece(pieceIndex):
                #we can request parts of this piece
                endgame = self.pieceStatus.inEndgame()
                neededRequests = conn.getMaxAmountOfInRequests() - conn.getAmountOfInRequests()
                neededRequests = self._makeRequestsForPieces(conn, neededRequests, (pieceIndex,), endgame)
                
                if neededRequests == 0:
                    #conn is filled
                    self.waitingConns.remove(conn)
                    
                if pieceIndex in self.requestedPieces:
                    #piece was requested again by now
                    if not self.requestedPieces[pieceIndex].isRequestable(endgame):
                        #no point in further trying
                        break
                    
                    
    def _tryRequestWithWaitingConns(self, oldConn, pieceIndex, offset, length):
        #called if a request failed to check if a waiting conn may do it
        success = False
        for conn in self.waitingConns.copy():
            #try one conn
            if conn.getStatus().hasPiece(pieceIndex):
                #peer has this piece
                if not conn.hasThisInRequest(pieceIndex, offset, length):
                    #but not this request, perfect
                    success = True
                    self.requestedPieces[pieceIndex].changeRequestConn(offset, oldConn, conn)
                    conn.addInRequest(pieceIndex, offset, length,
                                      failFunc=self.failedRequest,
                                      failFuncArgs=[conn, pieceIndex, offset, length])
                                    
                    if conn.getMaxAmountOfInRequests() - conn.getAmountOfInRequests() == 0:
                        self.waitingConns.remove(conn)
                    break
        return success
    
    
    ##external functions - requests
    
    def makeRequests(self, conn):
        assert not self.ownStatus.isFinished(), 'already seed but trying to request?!'
        self._makeRequestsForConn(conn)
        
                    
    def failedRequest(self, conn, pieceIndex, offset, length):
        #conn failed or got choked, try to pass request to a waiting conn
        if not self._tryRequestWithWaitingConns(conn, pieceIndex, offset, length):
            #couldn't find a waiting conn for this request
            request = self.requestedPieces[pieceIndex]
            request.failedRequest(offset, conn)

            if request.isEmpty():
                #not a single in progress piece, remove request object
                del self.requestedPieces[pieceIndex]
                self.pieceStatus.setConcurrentRequestsCounter((pieceIndex,), -1)
    
    
    def finishedRequest(self, data, conn, pieceIndex, offset):
        #finished a request
        assert not self.ownStatus.isFinished(), 'already seed but finished a request?!'
        finishedPiece = False
        request = self.requestedPieces[pieceIndex]
        
        try:
            self.storage.storeData(pieceIndex, data, offset)
            success = True
        except:
            self.log.error('Failed to store data of piece "%i", offset "%i":\n%s', pieceIndex, offset, logTraceback())
            success = False
        
        if not success:
            #failed to store data
            canceledConns = []
            request.failedRequest(offset, conn)
            
        else:
            #stored data
            canceledConns = request.finishedRequest(offset, conn)
            
            #check if request is finished
            if request.isFinished():
                #finished piece
                del self.requestedPieces[pieceIndex]
                
                #get data
                try:
                    pieceData = self.storage.getData(pieceIndex, 0, request.getPieceSize())
                except:
                    pieceData = ''
                    self.log.error('Failed to read data of piece "%i":\n%s', pieceIndex, logTraceback())
                
                #check data
                if sha(pieceData).digest() == self.torrent.getPieceHashByPieceIndex(pieceIndex):
                    #success
                    finishedPiece = True
                    self.ownStatus.gotPiece(pieceIndex)
                    self.pieceStatus.setConcurrentRequestsCounter((pieceIndex,), -2)
                else:
                    #failure
                    if not pieceData == '':
                        self.log.warn("Checksum error for retrieved piece %d!", pieceIndex)
                    self.pieceStatus.setConcurrentRequestsCounter((pieceIndex,), -1)
                    self._tryPieceWithWaitingConns(pieceIndex)
                    
        if self.ownStatus.isFinished():
            #clear waiting conns
            self.waitingConns.clear()
        else:
            #make requests for the current conn
            self._makeRequestsForConn(conn)
            
            #make requests for canceled ones
            for conn in canceledConns:
                self._makeRequestsForConn(conn)
                
        return finishedPiece
    

    def connGotUnchoked(self, conn):
        #conn got unchoked, make requests
        assert not self.ownStatus.isFinished(), 'already seed but trying to request?!'
        self._makeRequestsForConn(conn)
        

    def connGotChoked(self, conn):
        #conn got choked, if it was waiting for a request, remove it
        self.waitingConns.discard(conn)
        

    def connGotClosed(self, conn):
        #conn got completely closed, if it was waiting for a request, remove it
        self.waitingConns.discard(conn)
        
        
    def connGotNotInteresting(self, conn):
        #nothing to request from this conn anymore
        self.waitingConns.discard(conn)
        
        
    def reset(self):
        #pieces
        neededPieces = self.ownStatus.getNeededPieces()
        notNeededPieces = self.ownStatus.getGotPieces()
        notNeededPieces.update(self.ownStatus.getMissingPieces())
        notNeededPieces.difference_update(neededPieces)
        
        #abort requests
        canceledConns = set()
        requests = [pieceIndex for pieceIndex in self.requestedPieces if pieceIndex not in neededPieces]
        for pieceIndex in requests:
            self.log.debug('Aborting requests for piece %i', pieceIndex)
            canceledConns.update(self.requestedPieces[pieceIndex].abortAllRequests())
            del self.requestedPieces[pieceIndex]
            
        #change piece status
        neededPieces.difference_update(set(self.requestedPieces.iterkeys()))
        self.pieceStatus.setConcurrentRequestsCounter(notNeededPieces, -2)
        self.pieceStatus.setConcurrentRequestsCounter(neededPieces, -1)
                
        #make requests for conns with canceled requests
        for conn in canceledConns:
            self._makeRequestsForConn(conn)
            
            
    def getStats(self, **kwargs):
        stats = {}
        if kwargs.get('requestDetails', False):
            stats['requests'] = [req.getStats() for req in self.requestedPieces.itervalues()]
            
        if kwargs.get('pieceAverages', False):
            stats['requestedPieceAmount'] = len(self.requestedPieces)
            stats['avgReqPieceAvailability'] = (sum(self.pieceStatus.getAvailability(pieces=self.requestedPieces).itervalues()) * 1.0) / max(len(self.requestedPieces), 1)
        return stats