"""
Copyright 2009  Blub

Connection, a class which provides basic functionalities (sending and receiving messages, aborting sends, ...) and
BtConnection, a class which represents one connection to another bittorrent client and provides support for the
basic functionalities (choking, requests, ...).
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

from Conversion import peerIdToClient
from Logger import Logger
from Measure import Measure
from Status import Status
from Storage import StorageException
from Utilities import logTraceback
import Messages

from collections import deque
from time import time
import threading


class Connection:
    def __init__(self, connStatus, scheduler, conn, direction, remotePeerAddr,\
                 inMeasureParent, outMeasureParent, outLimiter, inLimiter,\
                 msgLenFunc, msgDecodeFunc, msgLengthFieldLen, maxMsgLength, keepaliveMsgFunc,\
                 log):
        
        self.sched = scheduler
        
        #connection
        self.conn = conn
        self.connIdent = self.conn.fileno()        
        self.connectTime = time()
        self.direction = direction      
        self.inMsgCount = 0
        self.closed = False
        
        #peer
        self.remotePeerAddr = remotePeerAddr
        
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
        
        #data buffer
        self.inBuffer = []
        self.outBufferQueue = deque()
        self.outBufferMessages = {}
        self.outBufferMessageId = 0
        
        #messages
        self.msgLenFunc = msgLenFunc
        self.msgDecodeFunc = msgDecodeFunc
        self.msgLengthFieldLen = msgLengthFieldLen
        self.maxMsgLength = maxMsgLength
        
        #log
        self.log = log
        
        #lock
        self.lock = threading.RLock()
        
        #events
        self.sendTimeoutEvent = self.sched.scheduleEvent(self.timeout, timedelta=300, funcArgs=['send timed out'])
        self.recvTimeoutEvent = self.sched.scheduleEvent(self.timeout, timedelta=300, funcArgs=['read timed out'])
        self.keepaliveEvent = self.sched.scheduleEvent(self.send, timedelta=100, funcArgs=[keepaliveMsgFunc()], repeatdelta=100)
        
        
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
            msgLen = self.msgLenFunc(data)
            while msgLen is not None:
                msgLen += self.msgLengthFieldLen #because of the length field
                if msgLen > self.maxMsgLength:
                    #way too large
                    self._fail('message from peer exceeds size limit (%i bytes)' % (self.maxMsgLength,))
                    msgLen = None
                    
                elif len(data) < msgLen:
                    #incomplete message
                    msgLen = None
                    
                else:
                    #finished a message
                    msg = self.msgDecodeFunc(data[:msgLen])
                    self._gotMessage(msg)
                    msgs.append((self.inMsgCount, msg))
                    self.inMsgCount += 1
                    data = data[msgLen:]
                    msgLen = self.msgLenFunc(data)
                    
            if data == '':
                #all processed
                self.inBuffer = []
            else:
                #still data left
                self.inBuffer = [data]
        return msgs


    def _gotMessage(self, msg):
        pass
        
    
    def _send(self):
        #really send the buffered data - or at least try to
        self.sched.rescheduleEvent(self.sendTimeoutEvent, timedelta=300)
        self.sched.rescheduleEvent(self.keepaliveEvent, timedelta=100)
        
        while len(self.outBufferQueue) > 0:
            messageId = self.outBufferQueue[0]
            if not messageId in self.outBufferMessages:
                #message send got aborted
                self.outBufferQueue.popleft()
                
                if len(self.outBufferQueue) == 0:
                    #nothing to send anymore, notify
                    self.connStatus.wantsToSend(False, self.connIdent)
                    
            else:
                #something to send
                message = self.outBufferMessages[messageId]
                messageLen = len(message[1])
                wantedBytes = min(messageLen, self.conn.getFreeOutBufferSpace())
                allowedBytes = self.outLimiter.claimUnits(self.connIdent, wantedBytes)
                
                if allowedBytes == 0:
                    #may not even send a single byte ...
                    break
                else:
                    #at least something may be send        
                    sendBytes = self.conn.send(message[1][:allowedBytes])
                    self.outRate.updateRate(sendBytes)
                    message[2] = True
                        
                    if sendBytes < messageLen:
                        #but not all was send
                        message[1] = message[1][sendBytes:]
                        break
                        
                    else:
                        #all was send
                        self.outBufferQueue.popleft()
                        del self.outBufferMessages[messageId]
                        
                        if len(self.outBufferQueue) == 0:
                            #nothing to send anymore, notify
                            self.connStatus.wantsToSend(False, self.connIdent)
                            
                        if message[0] is not None:
                            #execute
                            message[0]()
                            
                            
    def _queueSend(self, data, sendFinishedHandle=None):
        if len(self.outBufferQueue) == 0:
            #first queued item, notify about send interest
            self.connStatus.wantsToSend(True, self.connIdent)
        messageId = self.outBufferMessageId
        self.outBufferMessageId += 1
        self.outBufferQueue.append(messageId)
        self.outBufferMessages[messageId] = [sendFinishedHandle, data, False]
        return messageId
    
    
    def _abortSend(self, messageId):
        aborted = False
        message = self.outBufferMessages.get(messageId, None)
        if message is not None:
            #still queued
            if not message[2]:
                #send did not start up to now
                aborted = True
                del self.outBufferMessages[messageId]
        return aborted
                    
                    
    def _fail(self, reason=''):
        #cause the conn to fail
        self.log.info('Conn failed: %s', reason)
        self.conn.close(force=True)
        
        
    def _close(self):
        #set flag
        self.closed = True
        
        #close conn, update conn state
        self.conn.close(force=True)
        self.connStatus.removeConn(self.connIdent)
        
        #stop rate measurement
        self.inRate.stop()
        self.outRate.stop()
        
        #remove conn from limiter
        self.outLimiter.removeUser(self.connIdent)
        self.inLimiter.removeUser(self.connIdent)
        
        #clear buffers
        self.inBuffer = []
        self.outBufferQueue.clear()
        self.outBufferMessages.clear()
        self.outBufferMessageId = 0
        
        #remove events
        self.sched.removeEvent(self.sendTimeoutEvent)
        self.sched.removeEvent(self.recvTimeoutEvent)
        self.sched.removeEvent(self.keepaliveEvent)
        
        
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
        
        
    def sendEvent(self):
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
    
    
    ##external functions - get info

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
    
    
    def getPayloadRatio(self):
        self.lock.acquire()
        ratio = self._getPayloadRatio()
        self.lock.release()
        return ratio
    
        
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
    
    
    
    
class BtConnection(Connection):
    def __init__(self, torrentIdent, globalStatus, connStatus, remotePeerId, \
                 scheduler, conn, direction, remotePeerAddr,\
                 inMeasureParent, outMeasureParent, outLimiter, inLimiter):
                    
        log = Logger('BtConnection', '%-6s - %-6s -', torrentIdent, conn.fileno())
                 
        Connection.__init__(self, connStatus, scheduler, conn, direction, remotePeerAddr,\
                            inMeasureParent, outMeasureParent, outLimiter, inLimiter,\
                            Messages.getMessageLength, Messages.decodeMessage, 4, 140000, Messages.generateKeepAlive,\
                            log)
        
        #ident
        self.torrentIdent = torrentIdent
        
        #peer
        self.remotePeerId = remotePeerId
        self.remoteClient = peerIdToClient(remotePeerId)
        
        #piece status
        self.status = Status(globalStatus.getPieceAmount(), globalStatus)
        
        #choke and interest state
        self.localInterest = False
        self.remoteInterest = False
        self.localChoke = True
        self.remoteChoke = True
        
        #requests
        self.outRequestsInFlight = 0
        self.outRequestQueue = []
        self.outRequestHandles = {}
        self.maxInRequests = self._calculateMaxAmountOfInRequests()
        self.inRequestQueue = []
        self.inRequestInfo = {}
        
        #events
        self.requestTimeoutEvent = None
        
        
    ##internal functions - socket
    
    def _gotMessage(self, msg):
        if msg[0]==7:
            #a piece part
            if self._hasThisInRequest(msg[1][0], msg[1][1], len(msg[1][2])):
                #a valid one even
                assert self.requestTimeoutEvent is not None, 'got data for a request but no request timeout exists?!'
                if self._amountOfInRequests() == 1:
                    self.sched.removeEvent(self.requestTimeoutEvent)
                    self.requestTimeoutEvent = None
                else:
                    self.sched.rescheduleEvent(self.requestTimeoutEvent, timedelta=120)
                self.inRate.updatePayloadCounter(len(msg[1][2]))
                
                
    def _close(self):
        Connection._close(self)
        
        #clear piece status
        self.status.clear()
        
        #set interest and choke states to defaults
        self.localInterest = False
        self.remoteInterest = False
        self.localChoke = True
        self.remoteChoke = True
        
        #remove requests
        self._delAllOutRequests()        
        self._delAllInRequests()
        
    
    ##internal functions - inrequests
    
    def _addInRequest(self, pieceIndex, offset, length, callback=None, callbackArgs=[], callbackKw={}):
        assert self.remoteChoke==False, 'requesting but choked?!'
        
        #add timeout
        if self.requestTimeoutEvent is None:
            self.requestTimeoutEvent = self.sched.scheduleEvent(self.timeout, timedelta=120, funcArgs=['request timed out'])
            
        #add request
        messageId = self._queueSend(Messages.generateRequest(pieceIndex, offset, length))
        inRequest = (pieceIndex, offset, length)
        assert not inRequest in self.inRequestInfo, 'queueing an already queued request?!'
        self.inRequestQueue.append(inRequest)
        self.inRequestInfo[inRequest] = {'messageId':messageId,
                                         'func':callback,
                                         'funcArgs':callbackArgs,
                                         'funcKw':callbackKw}


    def _getInRequestsOfPiece(self, pieceIndex):
        requests = set([inRequest[1] for inRequest in self.inRequestQueue if inRequest[0] == pieceIndex])
        return requests
        
        
    def _finishedInRequest(self, pieceIndex, offset, length):
        #try to find the request and delete it if found
        inRequest = (pieceIndex, offset, length)
        self.inRequestQueue.remove(inRequest)
        del self.inRequestInfo[inRequest]
            
            
    def _cancelInRequest(self, pieceIndex, offset, length):
        #try to find the request, send cancel and then delete it
        inRequest = (pieceIndex, offset, length)
        self.inRequestQueue.remove(inRequest)
        requestInfo = self.inRequestInfo.pop(inRequest)
        if not self._abortSend(requestInfo['messageId']):
            #the request was already send
            self._queueSend(Messages.generateCancel(pieceIndex, offset, length))
        
        
    def _delAllInRequests(self):
        for requestInfo in self.inRequestInfo.itervalues():
            #call callback of failed request
            self._abortSend(requestInfo['messageId'])
            if requestInfo['func'] is not None:
                apply(requestInfo['func'], requestInfo['funcArgs'], requestInfo['funcKw'])
        self.inRequestQueue = []
        self.inRequestInfo = {}
        

    def _hasThisInRequest(self, pieceIndex, offset, length):
        return (pieceIndex, offset, length) in self.inRequestInfo
    
    
    def _amountOfInRequests(self):
        return len(self.inRequestQueue)
    
    
    def _calculateMaxAmountOfInRequests(self):
        if self.remoteClient.startswith('Azureus'):
            limit = 16
        
        elif self.remoteClient.startswith('I2PRufus'):
            limit = 16
            
        elif self.remoteClient.startswith('I2PSnark'):
            limit = 32
        
        elif self.remoteClient.startswith('PyBit') and ' ' in self.remoteClient:
            version = tuple((int(digit) for digit in self.remoteClient.split(' ')[1].split('.')))
            if version < (0, 0, 9):
                limit = 32
            else:
                limit = 64
            
        elif self.remoteClient.startswith('Robert'):
            limit = 31
            
        else:
            #I2P-Bt and unknown
            limit = 16
            
        return limit
        
    
    def _getMaxAmountOfInRequests(self):
        return self.maxInRequests
        
    
    ##internal functions - outrequests
    
    def _sendOutRequest(self):
        #queue one outrequest in the outbuffer
        outRequest = self.outRequestQueue.pop(0)
        try:
            #try to get data
            data = self.outRequestHandles.pop(outRequest)()
        except StorageException:
            #failed to get data
            self.log.error("Failed to get data for outrequest:\n%s", logTraceback())
            data = None
            self._fail("could not get data for outrequest")
            
        if data is not None:
            #got data
            if not len(data) == outRequest[2]:
                 self.log.error("Did not get enough data for outrequest: expected %i, got %i!", outRequest[2], len(data))
                 self._fail("could not get data for outrequest")
            else:
                message = Messages.generatePiece(outRequest[0], outRequest[1], data)
                self.outRate.updatePayloadCounter(outRequest[2])
                self.outRequestsInFlight += 1
                self._queueSend(message, self._outRequestGotSend)
        

    def _outRequestGotSend(self):
        self.outRequestsInFlight -= 1
        assert self.outRequestsInFlight == 0, 'multiple out requests in flight?!'
        assert len(self.outRequestQueue) == len(self.outRequestHandles), 'out of sync: queue length %i but %i handles!' % (len(self.outRequestQueue), len(self.outRequestHandles))
        if len(self.outRequestQueue) > 0 and self.outRequestsInFlight == 0:
            self._sendOutRequest()
        
        
    
    def _addOutRequest(self, pieceIndex, offset, length, dataHandle):
        self.outRequestQueue.append((pieceIndex, offset, length))
        self.outRequestHandles[(pieceIndex, offset, length)] = dataHandle
        if self.outRequestsInFlight == 0:
            #no outrequest is currently being send, send one directly
            self._sendOutRequest()
            
    
    def _hasThisOutRequest(self, pieceIndex, offset, length):
        return (pieceIndex, offset, length) in self.outRequestHandles
        
        
    def _getAmountOfOutRequests(self):
        return len(self.outRequestQueue)
    
    
    def _delOutRequest(self, pieceIndex, offset, length):
        #try to find the request and delete it if found
        outRequest = (pieceIndex, offset, length)
        if outRequest in self.outRequestHandles:
            self.outRequestQueue.remove(outRequest)
            del self.outRequestHandles[outRequest]
            
            
    def _delAllOutRequests(self):
        self.outRequestQueue = []
        self.outRequestHandles.clear()
    
    
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
    
    def _getScore(self):
        ratio = self._getPayloadRatio()
        score = ratio + (ratio * self.inRate.getAveragePayloadRate())
        return score
            
            
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
        
    
    def getMaxAmountOfInRequests(self):
        self.lock.acquire()
        value = self._getMaxAmountOfInRequests()
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
    
    
    def delOutRequest(self, pieceIndex, offset, length):
        self.lock.acquire()
        self._delOutRequest(pieceIndex, offset, length)
        self.lock.release()
    
        
    def getAmountOfOutRequests(self):
        self.lock.acquire()
        value = self._getAmountOfOutRequests()
        self.lock.release()
        return value
        
        
    ##external functions - get info
    
    def getStatus(self):
        self.lock.acquire()
        obj = self.status
        self.lock.release()
        return obj
    
    
    def getScore(self):
        self.lock.acquire()
        score = self._getScore()
        self.lock.release()
        return score
        
        
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
    
    
    ##external functions - stats
    
    def getStats(self):
        self.lock.acquire()
        stats = {}
        stats['id'] = self.connIdent
        stats['addr'] = self.conn.getpeername()
        stats['direction'] = self.direction
        stats['connectedInterval'] = time() - self.connectTime
        stats['peerProgress'] = self.status.getPercent()
        stats['peerClient'] = self.remoteClient
        stats['inRawBytes'] = self.inRate.getTotalTransferedBytes()
        stats['outRawBytes'] = self.outRate.getTotalTransferedBytes()
        stats['inPayloadBytes'] = self.inRate.getTotalTransferedPayloadBytes()
        stats['outPayloadBytes'] = self.outRate.getTotalTransferedPayloadBytes()
        stats['inRawSpeed'] = self.inRate.getCurrentRate()
        stats['outRawSpeed'] = self.outRate.getCurrentRate()
        stats['localInterest'] = self.localInterest
        stats['remoteInterest'] = self.remoteInterest
        stats['localChoke'] = self.localChoke
        stats['remoteChoke'] = self.remoteChoke
        stats['localRequestCount'] = len(self.inRequestQueue)
        stats['remoteRequestCount'] = self.outRequestsInFlight + len(self.outRequestQueue)
        stats['avgInRawSpeed'] = self.inRate.getAverageRate() * 1024
        stats['avgOutRawSpeed'] = self.outRate.getAverageRate() * 1024
        stats['avgInPayloadSpeed'] = self.inRate.getAveragePayloadRate() * 1024
        stats['avgOutPayloadSpeed'] = self.outRate.getAveragePayloadRate() * 1024
        stats['score'] = self._getScore()
        stats['payloadRatio'] = self._getPayloadRatio()
        stats['protocolOverhead'] = (100.0 * (stats['inRawBytes'] + stats['outRawBytes'] - stats['inPayloadBytes'] - stats['outPayloadBytes'])) / max(stats['inPayloadBytes'] + stats['outPayloadBytes'], 1.0)
        self.lock.release()
        return stats