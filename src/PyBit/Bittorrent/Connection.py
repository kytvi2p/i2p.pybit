"""
Copyright 2009  Blub

Connection, a class which represents one connection to another bittorrent client and
provides support for the basic functionalities.
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

from Measure import Measure
from Status import Status
from Utilities import logTraceback
import Messages

from collections import deque
from time import time
import logging
import threading


class Connection:
    def __init__(self, torrentIdent, connStatus, globalStatus, scheduler,\
                 conn, direction, remotePeerId, remotePeerAddr,\
                 inMeasureParent, outMeasureParent, outLimiter, inLimiter):
        
        self.sched = scheduler
        self.torrentIdent = torrentIdent
        
        #connection
        self.conn = conn
        self.connIdent = self.conn.fileno()        
        self.connectTime = time()
        self.direction = direction      
        self.inMsgCount = 0
        
        #peer
        self.remotePeerAddr = remotePeerAddr
        self.remotePeerId = remotePeerId
        
        #conn status
        self.connStatus = connStatus
        self.connStatus.addConn(self.connIdent)
        
        #limiter
        self.outLimiter = outLimiter
        self.outLimiter.addUser(self.connIdent, callback=self.connStatus.allowedToSend, callbackArgs=[self.connIdent])
        self.inLimiter = inLimiter
        self.inLimiter.addUser(self.connIdent, callback=self.connStatus.allowedToRecv, callbackArgs=[self.connIdent])
        
        #rate
        self.inRate = Measure(self.sched, 60, [inMeasureParent])
        self.outRate = Measure(self.sched, 60, [outMeasureParent])
        
        #piece status
        self.status = Status(globalStatus.getPieceAmount(), globalStatus)
        
        #choke and interest state, closed flag
        self.localInterest = False
        self.remoteInterest = False
        self.localChoke = True
        self.remoteChoke = True
        self.closed = False
        
        #data and request buffer
        self.inBuffer = []
        self.outBuffer = deque()
        self.outRequests = {'inFlight':0,
                            'requests':deque()}
        self.inRequests = []
        
        #log
        #self.log = logging.getLogger(torrentIdent+'-Conn '+str(self.connIdent))
        self.log = logging.getLogger(torrentIdent+'-Conn')
        
        #lock
        self.lock = threading.RLock()
        
        #events
        self.sendTimeoutEvent = self.sched.scheduleEvent(self.timeout, timedelta=300, funcArgs=['send timed out'])
        self.recvTimeoutEvent = self.sched.scheduleEvent(self.timeout, timedelta=300, funcArgs=['read timed out'])
        self.keepaliveEvent = self.sched.scheduleEvent(self.send, timedelta=100, funcArgs=[Messages.generateKeepAlive()], repeatdelta=100)


        
    ##internal functions - socket
    
    def _recv(self):
        #really recv data - or at least try to
        msgs = []
        self.sched.rescheduleEvent(self.recvTimeoutEvent, timedelta=300)
        wantedBytes = self.conn.getUsedInBufferSpace()    
        allowedBytes = self.inLimiter.claimUnits(self.connIdent, wantedBytes)
        
        if not allowedBytes==0:
            #may receive something, recv data
            data = self.conn.recv(allowedBytes)
            self.inRate.updateRate(len(data))
            self.inBuffer.append(data)
            data = ''.join(self.inBuffer)
            
            #process data    
            msgLen = Messages.getMessageLength(data)
            while msgLen is not None:
                msgLen += 4 #because of the length field
                if msgLen > 140000:
                    #way too large
                    self._fail('message from peer exceeds size limit (140000 bytes)')
                    msgLen = None
                    
                elif len(data) < msgLen:
                    #incomplete message
                    msgLen = None
                else:
                    #finished a message
                    msg = Messages.decodeMessage(data[:msgLen])
                    self._gotMessage(msg)
                    msgs.append((self.inMsgCount, msg))
                    self.inMsgCount += 1
                    data = data[msgLen:]
                    msgLen = Messages.getMessageLength(data)
                    
            if data == '':
                #all processed
                self.inBuffer = []
            else:
                #still data left
                self.inBuffer = [data]
        return msgs


    def _gotMessage(self, msg):
        if msg[0]==7:
            #a piece part
            if self._hasThisInRequest(msg[1][0], msg[1][1], len(msg[1][2])):
                #a valid one even
                self.inRate.updatePayloadCounter(len(msg[1][2]))
        
    
    def _send(self):
        #really send the buffered data - or at least try to
        self.sched.rescheduleEvent(self.sendTimeoutEvent, timedelta=300)
        self.sched.rescheduleEvent(self.keepaliveEvent, timedelta=100)
        
        while len(self.outBuffer) > 0:
            message = self.outBuffer.popleft()
            messageLen = len(message[1])
            wantedBytes = min(messageLen, self.conn.getFreeOutBufferSpace())
            allowedBytes = self.outLimiter.claimUnits(self.connIdent, wantedBytes)
            
            if allowedBytes == 0:
                #must not send a single byte ...
                self.outBuffer.appendleft(message)
                break
            else:
                #at least something may be send        
                sendBytes = self.conn.send(message[1][:allowedBytes])
                self.outRate.updateRate(sendBytes)
                    
                if sendBytes < messageLen:
                    #but not all was send
                    message[1] = message[1][sendBytes:]
                    self.outBuffer.appendleft(message)
                    break
                    
                else:
                    #all was send
                    if len(self.outBuffer) == 0:
                        #nothing to send anymore, notify
                        self.connStatus.wantsToSend(False, self.connIdent)
                        
                    if message[0] == 'outrequest':
                        #was a outrequest
                        self._outRequestGotSend()
                        

    def _queueSend(self, data, dataType='normal'):
        if len(self.outBuffer)==0:
            #first queued item, notify about send interest
            self.connStatus.wantsToSend(True, self.connIdent)
        self.outBuffer.append([dataType, data])
                    
                    
    def _fail(self, reason=''):
        #cause the conn to fail
        self.log.info('Conn failed: %s', reason)
        self.conn.close(forceClose=True)
        
        
    def _close(self):
        #set flag
        self.closed = True
        
        #close conn, update conn state
        self.conn.close(forceClose=True)
        self.connStatus.removeConn(self.connIdent)
        
        #stop rate measurement
        self.inRate.stop()
        self.outRate.stop()
        
        #remove conn from limiter
        self.outLimiter.removeUser(self.connIdent)
        self.inLimiter.removeUser(self.connIdent)
        
        #clear piece status
        self.status.clear()
        
        #set interest and choke states to defaults
        self.localInterest = False
        self.remoteInterest = False
        self.localChoke = True
        self.remoteChoke = True
        
        #clear buffers
        self.inBuffer = []
        self.outBuffer.clear()
        
        #remove requests
        self._delAllOutRequests()        
        self._delAllInRequests()
        
        #remove events
        self.sched.removeEvent(self.sendTimeoutEvent)
        self.sched.removeEvent(self.recvTimeoutEvent)
        self.sched.removeEvent(self.keepaliveEvent)
        
    
    ##internal functions - inrequests
    
    
    def _addInRequest(self, pieceIndex, offset, length, callback=None, callbackArgs=[], callbackKw={}):
        self.inRequests.append({'pieceIndex':pieceIndex,
                                'offset':offset,
                                'length':length,
                                'func':callback,
                                'funcArgs':callbackArgs,
                                'funcKw':callbackKw})
        
        self._queueSend(Messages.generateRequest(pieceIndex, offset, length))


    def _getInRequestsOfPiece(self, pieceIndex):
        requests = set()
        for i in xrange(0, len(self.inRequests)):
            if self.inRequests[i]['pieceIndex'] == pieceIndex:
                requests.add(self.inRequests[i]['offset'])
        return requests
    
        
    def _findInRequest(self, pieceIndex, offset, length):
        #try to find the request
        place = None
        for i in xrange(0, len(self.inRequests)):
            request = self.inRequests[i]
            if request['pieceIndex'] == pieceIndex and \
               request['offset'] == offset and \
               request['length'] == length:
                #found it
                place = i
                break;
        return place
        
        
    def _finishedInRequest(self, pieceIndex, offset, length):
        #try to find the request and delete it if found
        place = self._findInRequest(pieceIndex, offset, length)
        if place is not None:
            #found it, delete it
            request = self.inRequests[place]
            del self.inRequests[place]            
            
            
    def _cancelInRequest(self, pieceIndex, offset, length):
        #try to find the request, send cancel and then delete it
        place = self._findInRequest(pieceIndex, offset, length)
        if place is not None:
            #found it, send cancel and then delete it
            request = self.inRequests[place]
            self._queueSend(Messages.generateCancel(request['pieceIndex'], request['offset'], request['length']))
            del self.inRequests[place]
            
            
    def _cancelAllInRequests(self):
        for request in self.inRequests:
            #abort request
            self._queueSend(Messages.generateCancel(request['pieceIndex'], request['offset'], request['length']))
        self.inRequests = []
        
        
    def _delInRequest(self, pieceIndex, offset, length):
        #try to find the request, call callback and then delete it
        place = self._findInRequest(pieceIndex, offset, length)
        if place is not None:
            #found it, call callback and then delete it
            request = self.inRequests[place]
            del self.inRequests[place]
            if request['func'] is not None:
                apply(request['func'], request['funcArgs'], request['funcKw'])
            
        
        
    def _delAllInRequests(self):
        for request in self.inRequests:
            #call callback of failed request
            if request['func'] is not None:
                apply(request['func'], request['funcArgs'], request['funcKw'])
        self.inRequests = []
        

    def _hasThisInRequest(self, pieceIndex, offset, length):
        #try to find request
        place = self._findInRequest(pieceIndex, offset, length)
        return (place is not None)
    
    
    def _amountOfInRequests(self):
        return len(self.inRequests)
        
    
    ##internal functions - outrequests
    
    def _sendOutRequest(self):
        #queue one outrequest in the outbuffer
        outRequest = self.outRequests['requests'].popleft()
        try:
            #try to get data
            data = outRequest['dataHandle']()
        except:
            #failed to get data
            self.log.error("Failed to get data for outrequest:\n%s", logTraceback())
            data = None
            self._fail("could not get data for outrequest")
            
        if data is not None:
            #got data
            message = Messages.generatePiece(outRequest['pieceIndex'], outRequest['offset'], data)
            self.outRate.updatePayloadCounter(outRequest['length'])
            self.outRequests['inFlight'] += 1
            self._queueSend(message, 'outrequest')
        

    def _outRequestGotSend(self):
        self.outRequests['inFlight'] -= 1
        assert self.outRequests['inFlight'] == 0, 'multiple out requests in flight?!'
        if len(self.outRequests['requests']) > 0 and self.outRequests['inFlight']==0:
            self._sendOutRequest()
        
        
    
    def _addOutRequest(self, pieceIndex, offset, length, dataHandle):        
        self.outRequests['requests'].append({'pieceIndex':pieceIndex,
                                             'offset':offset,
                                             'length':length,
                                             'dataHandle':dataHandle})
        if self.outRequests['inFlight']==0:
            #no outrequest is currently being send, send one directly
            self._sendOutRequest()
            
    
    def _hasThisOutRequest(self, pieceIndex, offset, length):
        found = False
        #try to find the request
        for i in xrange(0, len(self.outRequests['requests'])):
            request = self.outRequests['requests'][i]
            if request['pieceIndex'] == pieceIndex and \
               request['offset'] == offset and \
               request['length'] == length:
                #found it
                found = True
                break;
            
        return found
        
        
    def _getAmountOfOutRequests(self):
        return len(self.outRequests['requests'])
    
    
    def _delOutRequest(self, pieceIndex, offset, length):
        #try to find the request and delete it if found
        for i in xrange(0, len(self.outRequests['requests'])):
            request = self.outRequests['requests'][i]
            if request['pieceIndex'] == pieceIndex and \
               request['offset'] == offset and \
               request['length'] == length:
                #found it
                del self.outRequests['requests'][i]
                break;
            
            
    def _delAllOutRequests(self):
        self.outRequests['requests'].clear()
    
    
    ##internal functions - choking and interest
    
    
    def _setLocalInterest(self, value):
        if value==False and self.localInterest==True:
            #changing to negative, we were interested before
            assert self._amountOfInRequests()==0,'Local Requests are running and we are not interested?'
            #self._cancelAllInRequests()
            self._queueSend(Messages.generateNotInterested())
            self.localInterest = value            
        elif value==True and self.localInterest==False:
            self._queueSend(Messages.generateInterested())
            self.localInterest = value
            

    def _setRemoteInterest(self, value):
        if value==False and self.remoteInterest==True:
            self.setLocalChoke(True)
            self.remoteInterest = value
            
        elif value==True and self.remoteInterest==False:
            self.remoteInterest = value
            
    
    def _setLocalChoke(self, value):
        if value==True and self.localChoke==False:
            #choking
            self._delAllOutRequests()
            self._queueSend(Messages.generateChoke())
            self.localChoke = value
            
        elif value==False and self.localChoke==True:
            self._queueSend(Messages.generateUnChoke())
            self.localChoke = value

    def _setRemoteChoke(self, value):
        if value==True and self.remoteChoke==False:
            #choked us, delete all incomming requests
            self._delAllInRequests()
            self.remoteChoke = value
            
        elif value==False and self.remoteChoke==True:
            self.remoteChoke = value
    
    
    ##internal functions - other
    
    def _getPayloadRatio(self):
        inPayload = self.inRate.getTotalTransferedPayloadBytes()
        outPayload = self.outRate.getTotalTransferedPayloadBytes()
        
        if inPayload == 0 and outPayload == 0:
            ratio = 1.0
        elif inPayload == 0 and outPayload != 0:
            ratio = 1.0/outPayload
        elif inPayload != 0 and outPayload == 0:
            ratio = inPayload/1.0
        else:
            ratio = inPayload / (outPayload * 1.0)
        return ratio
            
            
    ##external functions - socket
    
    def recv(self):
        self.lock.acquire()
        msgs = []
        if not self.closed:
            msgs = self._recv()
        self.lock.release()
        return msgs
            
    
    def send(self, data):
        self.lock.acquire()
        if not self.closed:
            self._queueSend(data)
        self.lock.release()
        
        
    def sendQueuedData(self):
        self.lock.acquire()
        if not self.closed:
            self._send()
        self.lock.release()
    
    
    def fileno(self):
        self.lock.acquire()
        value = self.connIdent
        self.lock.release()
        return value
    
    
    def timeout(self, reason):
        self.lock.acquire()
        if not self.closed:        
            self._fail(reason)
        self.lock.release()
        
        
    def close(self):
        self.lock.acquire()
        if not self.closed:
            self._close()
        self.lock.release()
    

    ##external functions - choking and interested

    def localChoked(self):
        self.lock.acquire()
        value = self.localChoke
        self.lock.release()
        return value
    
    
    def remoteChoked(self):
        self.lock.acquire()
        value = self.remoteChoke
        self.lock.release()
        return value
    
    
    def localInterested(self):
        self.lock.acquire()
        value = self.localInterest
        self.lock.release()
        return value
    
    
    def remoteInterested(self):
        self.lock.acquire()
        value = self.remoteInterest
        self.lock.release()
        return value
    
    
    def setLocalInterest(self, value):
        self.lock.acquire()
        if not self.closed:
            self._setLocalInterest(value)
        self.lock.release()
        
        
    def setRemoteInterest(self, value):
        self.lock.acquire()
        if not self.closed:
            self._setRemoteInterest(value)
        self.lock.release()            
        
        
    def setLocalChoke(self, value):
        self.lock.acquire()
        if not self.closed:
            self._setLocalChoke(value)
        self.lock.release()
        
        
    def setRemoteChoke(self, value):
        self.lock.acquire()
        if not self.closed:
            self._setRemoteChoke(value)
        self.lock.release()
        
    
    ##external functions - inrequests
    
    
    def addInRequest(self, pieceIndex, offset, length, failFunc=None, failFuncArgs=[], failFuncKw={}):
        self.lock.acquire()
        assert (not self.remoteChoke),'uhm, we are not allowed to make requests?!'
        if not self.closed:
            self._addInRequest(pieceIndex, offset, length, failFunc, failFuncArgs, failFuncKw)
        self.lock.release()


    def getInRequestsOfPiece(self, pieceIndex):
        self.lock.acquire()
        requests = self._getInRequestsOfPiece(pieceIndex)
        self.lock.release()
        return requests
     
        
    def finishedInRequest(self, pieceIndex, offset, length):
        self.lock.acquire()
        if not self.closed:
            self._finishedInRequest(pieceIndex, offset, length)
        self.lock.release()
            
            
    def cancelInRequest(self, pieceIndex, offset, length):
        self.lock.acquire()
        if not self.closed:
            self._cancelInRequest(pieceIndex, offset, length)
        self.lock.release()
            
            
    def cancelAllInRequests(self):
        self.lock.acquire()
        if not self.closed:
            self._cancelAllInRequests()
        self.lock.release()
        
        
    def delInRequest(self, pieceIndex, offset, length):
        self.lock.acquire()
        if not self.closed:
            self._delInRequest(pieceIndex, offset, length)
        self.lock.release()
        
        
    def delAllInRequests(self):
        self.lock.acquire()
        if not self.closed:
            self._delAllInRequests()
        self.lock.release()
        

    def hasThisInRequest(self, pieceIndex, offset, length):
        self.lock.acquire()
        value = self._hasThisInRequest(pieceIndex, offset, length)
        self.lock.release()
        return value
    
    
    def getAmountOfInRequests(self):
        self.lock.acquire()
        value = self._amountOfInRequests()
        self.lock.release()
        return value
        
    
    ##internal functions - outrequests
    
    def addOutRequest(self, pieceIndex, offset, length, dataHandle):
        self.lock.acquire()
        if not self.closed:
            self._addOutRequest(pieceIndex, offset, length, dataHandle)
        self.lock.release()
        
    
    def hasThisOutRequest(self, pieceIndex, offset, length):
        self.lock.acquire()
        value = self._hasThisOutRequest(pieceIndex, offset, length)
        self.lock.release()
        return value
    
        
    def getAmountOfOutRequests(self):
        self.lock.acquire()
        value = self._getAmountOfOutRequests()
        self.lock.release()
        return value
    
    
    def delOutRequest(self, pieceIndex, offset, length):
        self.lock.acquire()
        if not self.closed:
            self._delOutRequest(pieceIndex, offset, length)
        self.lock.release()
        
            
    def delAllOutRequests(self):
        self.lock.acquire()
        if not self.closed:
            self._delAllOutRequests()
        self.lock.release()
        

    ##external functions - other

    def getInRate(self):
        self.lock.acquire()
        rate = self.inRate
        self.lock.release()
        return rate
    

    def getOutRate(self):
        self.lock.acquire()
        rate = self.outRate
        self.lock.release()
        return rate


    def getStatus(self):
        self.lock.acquire()
        obj = self.status
        self.lock.release()
        return obj
    
    
    def getPayloadRatio(self):
        self.lock.acquire()
        ratio = self._getPayloadRatio()
        self.lock.release()
        return ratio
    
    
    def getScore(self):
        self.lock.acquire()
        ratio = self._getPayloadRatio()
        score = ratio + (ratio * self.inRate.getAveragePayloadRate())
        self.lock.release()
        return score
    
        
    def getRemotePeerAddr(self):
        self.lock.acquire()
        value = self.remotePeerAddr
        self.lock.release()
        return value
    
    
    def getShortRemotePeerAddr(self):
        self.lock.acquire()
        value = self.remotePeerAddr[:10]
        self.lock.release()
        return value
    
    
    def getRemotePeerId(self):
        self.lock.acquire()
        value = self.remotePeerId
        self.lock.release()
        return value
    
    
    def getTorrentIdent(self):
        self.lock.acquire()
        value = self.torrentIdent
        self.lock.release()
        return value

    
    def getInMsgCount(self):
        self.lock.acquire()
        value = self.inMsgCount
        self.lock.release()
        return value
    
    
    ##external functions - stats
    
    def getStats(self):
        self.lock.acquire()
        stats = {}
        stats['addr'] = self.conn.getpeername()
        stats['direction'] = self.direction
        stats['connectedInterval'] = time() - self.connectTime
        stats['peerProgress'] = self.status.getPercent()
        stats['inPayloadBytes'] = self.inRate.getTotalTransferedPayloadBytes()
        stats['outPayloadBytes'] = self.outRate.getTotalTransferedPayloadBytes()
        stats['inRawSpeed'] = self.inRate.getCurrentRate()
        stats['outRawSpeed'] = self.outRate.getCurrentRate()
        stats['localInterest'] = self.localInterest
        stats['remoteInterest'] = self.remoteInterest
        stats['localChoke'] = self.localChoke
        stats['remoteChoke'] = self.remoteChoke
        stats['localRequestCount'] = len(self.inRequests)
        stats['remoteRequestCount'] = self.outRequests['inFlight'] + len(self.outRequests['requests'])
        self.lock.release()
        return stats