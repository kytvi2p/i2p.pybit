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

from collections import deque
from sha import sha
import logging

from Request import Request
from Utilities import logTraceback


class Requester:
    def __init__(self, ident, globalStatus, storage, torrent):
        self.storage = storage
        self.torrent = torrent
        self.globalStatus = globalStatus
        self.ownStatus = storage.getStatus()
        #pieces
        self.requestablePieces = {-1:self.ownStatus.getMissingPieces()} #pieces which contain requestable parts
        self.requestedPieces = {} #pieces which are (partly) requested

        #conns
        self.waitingConns = set() #connections which allow request and are not filled
        
        self.log = logging.getLogger(ident+'-Requester')


    ##internal functions - requestable pieces

    def _endgame(self):
        return len(self.requestablePieces[-1])==0 and len(self.requestablePieces[0])==0


    def _removeRequestablePiece(self, pieceIndex, fromCount):
        self.requestablePieces[fromCount].remove(pieceIndex)


    def _moveRequestablePiece(self, pieceIndex, fromCount, toCount):
        self.log.debug("Moving piece %d from %d to %d",pieceIndex, fromCount, toCount)
        self.requestablePieces[fromCount].remove(pieceIndex)
        if toCount in self.requestablePieces:
            self.requestablePieces[toCount].add(pieceIndex)
        else:
            self.requestablePieces[toCount] = set((pieceIndex,))
            

    def _getRequestablePieces(self):
        self.log.debug("Still to fetch: %s", sorted(list(self.requestablePieces[-1])))
        if not self._endgame():
            #still pieces without a request
            if 0 in self.requestablePieces:
                #there are in progress pieces
                self.log.debug("got in-progress pieces: %s", str(self.requestablePieces[0]))
                pieces = deque((self.requestablePieces[0], self.requestablePieces[-1]))
            else:
                #just starting
                self.log.debug("no in-progress pieces")
                pieces = deque((self.requestablePieces[-1],))
        else:
            #endgame
            self.log.debug("endgame mode")
            pieces = deque(self.requestablePieces.itervalues())
        return pieces
            
    
    def _makeRequestsForPiece(self, conn, neededRequests, pieceIndex, endgame):
        assert neededRequests > 0,'requesting 0 requests?!'
        #try to make requests for this one piece
        if not pieceIndex in self.requestedPieces:
            #first request for this piece
            assert endgame==False,'Endgame but still pieces left?!'
            self._moveRequestablePiece(pieceIndex, -1, 0)
            requestObj = Request(pieceIndex, self.torrent.getLengthOfPiece(pieceIndex), 16384)
            self.requestedPieces[pieceIndex] = requestObj
            requests, oldMinReqCount, newMinReqCount = requestObj.getRequests(neededRequests, conn)
            assert len(requests) > 0,str(pieceIndex)+': new request but nothing requestable?!'
        else:
            #a request obj exists
            requestObj = self.requestedPieces[pieceIndex]
            excludeRequests = conn.getInRequestsOfPiece(pieceIndex)
            requests, oldMinReqCount, newMinReqCount = requestObj.getRequests(neededRequests, conn, excludeRequests, endgame)

        if len(requests) > 0:
            #got some valid requests
            for request in requests:
                #add request
                self.log.info('Making request for conn %d: piece %d, offset %d, length %d', conn.fileno(), pieceIndex, request[0], request[1])
                conn.addInRequest(pieceIndex, request[0], request[1],
                                  failFunc=self.failedRequest,
                                  failFuncArgs=[conn, pieceIndex, request[0], request[1]])
                neededRequests -= 1

            if oldMinReqCount != newMinReqCount:
                #need to move piece index
                self._moveRequestablePiece(pieceIndex, oldMinReqCount, newMinReqCount)
        return len(requests)
    

    def _makeRequestsForConn(self, conn):
        #try to fill conn with requests
        endgame = self._endgame()
        neededRequests = 8 - conn.getAmountOfInRequests()
        connStatus = conn.getStatus()
        requestablePieces = self._getRequestablePieces()
        
        while neededRequests > 0 and len(requestablePieces) > 0:
            #process one level of possible request (share same number of simultaneous requests)
            possiblePieces = connStatus.getMatchingGotPieces(requestablePieces.popleft())
            self.log.debug("Requestable pieces: %s", str(sorted(list(possiblePieces))))
            while neededRequests > 0 and len(possiblePieces) > 0:
                #get rarest piece - until one works or we run out of pieces
                pieceIndex = self.globalStatus.getRarest(possiblePieces)
                possiblePieces.remove(pieceIndex)
                neededRequests -= self._makeRequestsForPiece(conn, neededRequests, pieceIndex, endgame)

        if neededRequests > 0 and (not endgame) and self._endgame():
            #moved from no endgame to endgame, new requests may be available
            self._makeRequestsForConn(conn)
        else:
            #finished with this conn
            if neededRequests > 0:
                #couldn't get enough requests
                self.waitingConns.add(conn)
            else:
                #conn is filled
                self.waitingConns.discard(conn)


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
                                    
                    if 8 - conn.getAmountOfInRequests() == 0:
                        self.waitingConns.remove(conn)
                    break
        return success
    
    
    def _tryPieceWithWaitingConns(self, pieceIndex):
        #called if a whole piece failed, checks if some of the waiting conns may process this piece
        endgame = len(self.requestablePieces[-1]) <= 1 and len(self.requestablePieces[0]) == 0#if 1 then its this piece
        
        for conn in self.waitingConns.copy():
            #try one conn
            if conn.getStatus().hasPiece(pieceIndex):
                neededRequests = 8 - conn.getAmountOfInRequests()
                neededRequests -= self._makeRequestsForPiece(conn, neededRequests, pieceIndex, endgame)
                
                if neededRequests==0:
                    #conn is filled
                    self.waitingConns.remove(conn)
                    
                if pieceIndex in self.requestedPieces:
                    #piece was requested again by now
                    if not self.requestedPieces.isRequestable(endgame):
                        #no point in further trying
                        break
                    
    def failedRequest(self, conn, pieceIndex, offset, length):
        #conn failed or got choked, try to pass request to a waiting conn
        if not self._tryRequestWithWaitingConns(conn, pieceIndex, offset, length):
            #couldn't find a waiting conn for this request
            request = self.requestedPieces[pieceIndex]
            oldMinReqCount, newMinReqCount = request.failedRequest(offset, conn)

            if oldMinReqCount != newMinReqCount:
                #need to move piece index
                self._moveRequestablePiece(pieceIndex, oldMinReqCount, newMinReqCount)

            if request.isEmpty():
                #not a single in progress piece, remove request object
                del self.requestedPieces[pieceIndex]
                self._moveRequestablePiece(pieceIndex, 0, -1)
    

    def finishedRequest(self, data, conn, pieceIndex, offset):
        #finished a request
        assert not self.ownStatus.isSeed(), 'already seed but finished a request?!'
        finishedPiece = False
        
        try:
            self.storage.storeData(pieceIndex, data, offset)
            success = True
        except:
            self.log.error('Failed to store data of piece "%i", offset "%i":\n%s', pieceIndex, offset, logTraceback())
            success = False
        
        request = self.requestedPieces[pieceIndex]
        
        if not success:
            #failed to store data
            canceledConns = []
            oldMinReqCount, newMinReqCount = request.failedRequest(offset, conn)
            if oldMinReqCount != newMinReqCount:
                #need to move piece index
                self._moveRequestablePiece(pieceIndex, oldMinReqCount, newMinReqCount)
        
        else:
            #stored data
            canceledConns, oldMinReqCount, newMinReqCount = request.finishedRequest(offset, conn)

            if oldMinReqCount != newMinReqCount:
                #need to move piece index
                self._moveRequestablePiece(pieceIndex, oldMinReqCount, newMinReqCount)

            #check if request is finished
            if request.isFinished():
                #finished piece
                assert newMinReqCount==0,'Finished but running requests?!'
                del self.requestedPieces[pieceIndex]
                
                #get data
                try:
                    pieceData = self.storage.getData(pieceIndex, 0, request.getPieceSize())
                except:
                    pieceData = None
                    self.log.error('Failed to read data of piece "%i":\n%s', pieceIndex, logTraceback())
                
                #check data
                if pieceData is None:
                    validPiece = False
                else:
                    validPiece = sha(pieceData).digest() == self.torrent.getPieceHashByPieceIndex(pieceIndex)
                
                #act accordingly
                if validPiece:
                    #success
                    finishedPiece = True
                    self.ownStatus.gotPiece(pieceIndex)
                    self._removeRequestablePiece(pieceIndex, newMinReqCount)
                else:
                    #failure
                    self.log.warn("Checksum error for retrieved piece %d!", pieceIndex)
                    self._moveRequestablePiece(pieceIndex, 0, -1)
                

        if self.ownStatus.isSeed():
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
        assert not self.ownStatus.isSeed(), 'already seed but trying to request?!'
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
        self.requestablePieces = {-1:self.ownStatus.getMissingPieces()} #pieces which contain requestable parts
        self.requestedPieces = {} #pieces which are (partly) requested

        #conns
        self.waitingConns = set() #connections which allow request and are not filled
        
