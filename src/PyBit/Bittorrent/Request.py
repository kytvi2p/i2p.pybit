"""
Copyright 2009  Blub

Request, a class which keeps track of the requests for a single piece of a torrent.
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

class Request:
    def __init__(self, pieceIndex, pieceSize, requestSize):
        self.pieceIndex = pieceIndex
        self.pieceSize = pieceSize
        self.requestSize = requestSize
        self.requests = {}        #possible requests for this piece
        self.neededReqs = set()   #requests which are still needed
        self.curReqs = set()      #requests with lowest number of running requests        
        self.minReqCount = 0      #lowest number of simultaneous running requests

        #add requests
        offset = 0
        while offset + requestSize < pieceSize:
            self.requests[offset] = {'reqSize':requestSize,
                                     'reqCount':0,
                                     'reqConns':set()}
            self.neededReqs.add(offset)
            self.curReqs.add(offset)
            
            offset += requestSize

        self.requests[offset] = {'reqSize':pieceSize - offset,
                                 'reqCount':0,
                                 'reqConns':set()}
        self.neededReqs.add(offset)
        self.curReqs.add(offset)
        
        
    def _refillCurReqs(self):
        self.curReqs = set([offset for offset in self.neededReqs if self.requests[offset]['reqCount']==self.minReqCount])
        

    def _getRequest(self, conn, exclude):
        reqSize = None
        reqOffset = None

        #try to find a request
        for offset in self.curReqs:
            if not offset in exclude:
                #allowed request
                reqOffset = offset
                break

        if reqOffset is not None:
            #found a valid request
            request = self.requests[reqOffset]
            request['reqCount'] += 1
            assert not conn in request['reqConns'],'Assigning the same request twice to the same conn?!'
            request['reqConns'].add(conn)
            reqSize = request['reqSize']
            
            self.curReqs.remove(reqOffset)        
            if len(self.curReqs)==0:
                #refill
                self.minReqCount += 1
                self._refillCurReqs()
        
        return reqOffset, reqSize


    def _changeRequestConn(self, reqOffset, oldConn, newConn):
        funcs = self.requests[reqOffset]['reqConns']
        funcs.remove(oldConn)
        funcs.add(newConn)

    def _finishedRequest(self, reqOffset, conn):
        request = self.requests[reqOffset]
        #call cancel functions
        request['reqConns'].remove(conn)
        for conn in request['reqConns']:
            conn.cancelInRequest(self.pieceIndex, reqOffset, request['reqSize'])
        conns = request['reqConns'].copy()
        request['reqConns'].clear()

        #remove request
        self.neededReqs.remove(reqOffset)
        if reqOffset in self.curReqs:
            self.curReqs.remove(reqOffset)
            if len(self.neededReqs)==0:
                #completely finished
                self.minReqCount = 0
            else:
                while len(self.curReqs)==0:
                    #refill
                    self.minReqCount += 1
                    self._refillCurReqs()
        return conns


    def _pushRequest(self, reqOffset, conn):
        request = self.requests[reqOffset]
        request['reqConns'].remove(conn)
        request['reqCount'] -= 1
        count = request['reqCount']
        if count==self.minReqCount:
            #readd to curReqs
            assert reqOffset not in self.curReqs,'just reached same minReqCount but already in curReqs list?!'
            self.curReqs.add(reqOffset)
            
        elif count < self.minReqCount:
            #rebuild curReqs list
            assert count==self.minReqCount-1,'Jumped minReqCount?!'
            self.minReqCount -= 1
            self._refillCurReqs()


    def getRequests(self, num, conn, exclude=None, endgame=False):
        if exclude is None:
            exclude = set()
            
        oldMinReqCount = self.minReqCount
        requests = []
        request = self._getRequest(conn, exclude)
        while request[0] is not None and len(requests) < num-1 and (endgame or self.minReqCount==0):
            exclude.add(request[0])
            requests.append(request)
            request = self._getRequest(conn, exclude)
            
        if request[0] is not None:
            requests.append(request)
            
        return requests, oldMinReqCount, self.minReqCount


    def changeRequestConn(self, offset, oldConn, newConn):
        self._changeRequestConn(offset, oldConn, newConn)
    

    def failedRequest(self, offset, connId):
        oldMinReqCount = self.minReqCount
        self._pushRequest(offset, connId)
        return oldMinReqCount, self.minReqCount


    def finishedRequest(self, offset, conn):
        oldMinReqCount = self.minReqCount
        conns = self._finishedRequest(offset, conn)
        return conns, oldMinReqCount, self.minReqCount


    def getMinReqCount(self):
        return self.minReqCount


    def getPieceSize(self):
        return self.pieceSize


    def isEmpty(self):
        return (self.minReqCount==0 and len(self.requests)==len(self.curReqs))
    
    
    def isRequestable(self, endgame):
        return (len(self.neededReqs)>0 and (endgame or self.minReqCount==0))
    

    def isFinished(self):
        return (len(self.neededReqs)==0)
