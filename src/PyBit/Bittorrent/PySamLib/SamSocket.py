"""
Copyright 2009  Blub

SamTcpSocket, a collection of classes which represent sam sockets
This file is part of PySamLib.

PySamLib is free software: you can redistribute it and/or modify
it under the terms of the GNU Lesser General Public License as published
by the Free Software Foundation, version 2.1 of the License.

PySamLib is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Lesser General Public License for more details.

You should have received a copy of the GNU Lesser General Public License
along with PySamLib.  If not, see <http://www.gnu.org/licenses/>.
"""

from collections import deque

import SamMessages


class SamTcpListeningSocket:
    def __init__(self, i2pSockStatus, connId, initConnIds=None):
        self.i2pSockStatus = i2pSockStatus
        self.connId = connId
        self.newInSockets = deque()
        
        if initConnIds is not None:
            for connId in initConnIds:
                self.newInSockets.append(connId)
                self.i2pSockStatus.setRecvable(True, self.connId)
                
                
    def accept(self, max):
        if max==-1 or max >= len(self.newInSockets):
            newConns = list(self.newInSockets)
            self.newInSockets.clear()
            if len(newConns) > 0:
                self.i2pSockStatus.setRecvable(False, self.connId)
                        
        else:
            newConns = []
            count = 0
            while count < max:
                newConns.append(self.newInSockets.popleft())
                count += 1
        return newConns
    
    
    def clear(self):
        if len(self.newInSockets) > 0:
            self.i2pSockStatus.setRecvable(False, self.connId)
        self.newInSockets.clear()
        
                
    def acceptEvent(self, connId, remoteDest):
        self.newInSockets.append((connId, remoteDest))
        if len(self.newInSockets)==1:
            #first, add to listen socket to recvable list
            self.i2pSockStatus.setRecvable(True, self.connId)




class SamTcpSocket:
    def __init__(self, sendFunc, removeFunc, i2pSockStatus, connId, samId, direction, remoteDest, 
                 inMaxQueueSize, outMaxQueueSize, inRecvLimitThreshold):
        self.sendFunc = sendFunc     #func to send message
        self.removeFunc = removeFunc #func which does the final cleanup after close
        self.i2pSockStatus = i2pSockStatus
        
        #socket - fixed
        self.connId = connId #external id
        self.samId = samId   #sam id
        self.direction = direction
        self.remoteDest = remoteDest
        
        #socket - state
        self.connected = False
        self.waitingForClose = False
        self.errorReason = None
        self.sendable = False
        
        #socket - queue - in
        self.inQueue = deque()
        self.inQueueSize = 0
        self.inMaxQueueSize = inMaxQueueSize
        self.inBytesReceived = 0
        self.inRecvLimit = 0
        self.inRecvLimitThreshold = inRecvLimitThreshold
        
        #socket - queue - out
        self.outMessage = None
        self.outQueue = deque()
        self.outQueueSize = 0
        self.outMaxQueueSize = outMaxQueueSize
        
        
    ##internal functions
    
    def _close(self):
        #called once the socket should be finally really closed
        if self.inQueueSize > 0:
            #not empty receive buffer
            self.i2pSockStatus.setRecvable(False, self.connId)
            
        if self.errorReason is None and self.connected and (not self.waitingForClose) and self.outQueueSize < self.outMaxQueueSize:
            #socket did not fail up to now, was not waiting for close and has free space in its send buffer => it was sendable
            self.i2pSockStatus.setSendable(False, self.connId)
            
        if self.errorReason is not None:
            #socket failed
            self.i2pSockStatus.setErrored(False, self.connId)
        else:
            #socket was ok
            assert self.samId is not None, 'uhm, we need the id ...'
            self.sendFunc(SamMessages.streamCloseMessage(self.samId))
            
        self.removeFunc(self.connId)
        
        
    ##external functions - actions
    
    def connect(self, remoteDest=None):
        #called if the socket should send a connect message
        if remoteDest is not None:
            self.remoteDest = remoteDest
        assert self.remoteDest is not None, 'uhm, we need a destination ...'
        self.sendFunc(SamMessages.streamConnectMessage(self.samId, self.remoteDest))
        
    
    def send(self, data):
        #called to queue data for send in outbound queue
        allowedBytes = self.outMaxQueueSize - self.outQueueSize
        bytesToSend = len(data)
        
        #put data into queue
        if allowedBytes >= bytesToSend:
            #put everything into the queue
            self.outQueue.append(data)
            bytesSend = bytesToSend
        else:
            #too large, only take a part
            self.outQueue.append(data[:allowedBytes])
            bytesSend = allowedBytes
        
        self.outQueueSize += bytesSend
        
        #check if queue full
        if self.outQueueSize >= self.outMaxQueueSize:
            #buffer filled
            self.i2pSockStatus.setSendable(False, self.connId)
            
        #check if sendable
        if self.sendable:
            self.sendEvent()
        return bytesSend
            
    
    def recv(self, maxBytes, peekOnly):
        #called to recv data out of inbound queue
        availableBytes = self.inQueueSize
        
        if maxBytes == -1 or availableBytes <= maxBytes:
            #take everything available
            data = ''.join(self.inQueue)
            if not peekOnly:
                self.inQueue.clear()
                self.inQueueSize = 0
                self.i2pSockStatus.setRecvable(False, self.connId)
                
        else:
            #too much, only take a part
            data = deque()
            dataSize = 0
            count = 0
            while dataSize < maxBytes:
                #add chunks until the limit is reached
                if peekOnly:
                    dataChunk = self.inQueue[count]
                    count += 1
                else:
                    dataChunk = self.inQueue.popleft()
                dataChunkLen = len(dataChunk)
                if dataSize + dataChunkLen < maxBytes:
                    #take entire chunk
                    data.append(dataChunk)
                    dataSize += dataChunkLen
                    if not peekOnly:
                        self.inQueueSize -= dataChunkLen
                else:
                    #only take a part of the chunk
                    useableDataChunkLen = maxBytes - dataSize
                    data.append(dataChunk[:useableDataChunkLen])
                    dataSize += useableDataChunkLen
                    if not peekOnly:
                        self.inQueue.appendleft(dataChunk[useableDataChunkLen:])
                        self.inQueueSize -= useableDataChunkLen
                    
            data = ''.join(data)
        
        allowedBytes = self.inMaxQueueSize - self.inQueueSize
        if allowedBytes > 0:
            #free buffer space above threshold
            recvLimit = allowedBytes + self.inBytesReceived
            if self.samId is not None and recvLimit > (self.inRecvLimitThreshold + self.inRecvLimit):
                #new recv limit, notify sam bridge, if connected
                self.inRecvLimit = recvLimit
                self.sendFunc(SamMessages.streamReceiveLimitMessage(self.samId, recvLimit)) 
        
        return data
    
    
    ##external functions - events
    
    def connectEvent(self):
        #called when the socket connects
        self.connected = True
        self.sendable = True
        self.inRecvLimit = self.inMaxQueueSize
        self.i2pSockStatus.setSendable(True, self.connId)
        self.sendFunc(SamMessages.streamReceiveLimitMessage(self.samId, self.inRecvLimit))
        
    
    def errorEvent(self, reason):
        #called when the socket fails
        if self.waitingForClose:
            #was actually pending for close
            self._close()
        
        else:
            #socket status sets
            if self.connected and self.outQueueSize < self.outMaxQueueSize:
                self.i2pSockStatus.setSendable(False, self.connId)
            self.i2pSockStatus.setErrored(True, self.connId)
            
            #set samSocket status
            self.connected = False
            self.errorReason = reason
            self.outMessage = None,
            self.outQueue.clear()
            self.outQueueSize = 0
            self.sendable = False
            self.samId = None
    
    
    def sendEvent(self):
        #called to send data out of the outbound queue - triggered when the sam bridge allows further sending
        self.sendable = True
        
        if self.outQueueSize == 0:
            #nothing to send
            data = None
            if self.waitingForClose:
                #was waiting for close and done sending, so close it now
                self._close()
            
        elif self.outQueueSize <= 32768:
            #fits into a single message
            data = ''.join(self.outQueue)
            dataSize = len(data)
            self.outQueue.clear()
            self.outQueueSize = 0
            
        else:
            #too much data for a single message
            data = deque()
            dataSize = 0
            while dataSize < 32768:
                #add chunks until the limit is reached
                dataChunk = self.outQueue.popleft()
                dataChunkLen = len(dataChunk)
                if dataSize + dataChunkLen < 32768:
                    #take entire chunk
                    data.append(dataChunk)
                    dataSize += dataChunkLen
                    self.outQueueSize -= dataChunkLen
                else:
                    #only take a part of the chunk
                    useableDataChunkLen = 32768 - dataSize
                    data.append(dataChunk[:useableDataChunkLen])
                    self.outQueue.appendleft(dataChunk[useableDataChunkLen:])
                    self.outQueueSize -= useableDataChunkLen
                    dataSize += useableDataChunkLen
            data = ''.join(data)
            
        if data is not None:
            #something to send
            if (not self.waitingForClose) and \
               self.outQueueSize < self.outMaxQueueSize and \
               (self.outQueueSize + dataSize) >= self.outMaxQueueSize:
                #buffer was full and is not full anymore
                self.i2pSockStatus.setSendable(True, self.connId)
                
            #send data to the sam bridge
            self.sendFunc(SamMessages.streamSendMessage(self.samId, data))   
            
            #remember data, in case sam rejects it
            self.outMessage = data
            
            #don't send anything until the sam bridge send us its status
            self.sendable = False
            
            
    def sendSucceededEvent(self):
        #called if the sam bridge acknowledged a send
        self.outMessage = None
            
            
    def sendFailedEvent(self):
        #called if a send failed to requeue data at the beginning of the outgoing queue
        if self.errorReason is None:
            self.outQueue.appendleft(self.outMessage)
            self.outQueueSize += len(self.outMessage)
            
            if (not self.waitingForClose) and \
               self.outQueueSize >= self.outMaxQueueSize and \
               (self.outQueueSize - len(self.outMessage)) < self.outMaxQueueSize:
                #buffer was not full and is now full again
                self.i2pSockStatus.setSendable(False, self.connId)
        
    
    def recvEvent(self, data):
        #called to add data to the inbound queue
        dataSize = len(data)
        
        if self.inQueueSize == 0:
            #inbound buffer was empty until now, add socket to recvable set
            self.i2pSockStatus.setRecvable(True, self.connId)
        self.inQueue.append(data)
        self.inQueueSize += dataSize
        self.inBytesReceived += dataSize
        
    
    def close(self, force):
        #called once the socket should be close
        if self.errorReason is None:
            #socket did not fail up to now
            if (not force) and self.outQueueSize > 0:
                #still something left to send, wait with closing but set flag
                if not self.waitingForClose:
                    if self.outQueueSize < self.outMaxQueueSize:
                        self.i2pSockStatus.setSendable(False, self.connId)
                    self.waitingForClose = True
            else:
                #nothing left to send, close
                self._close()
        else:
            #socket failed already, do final cleanup
            self._close()
            
            
    ##external functions - info
    
    def getRemoteDestination(self):
        return self.remoteDest
    
    
    def getUsedInBufferSpace(self):
        return self.inQueueSize
    
    
    def getFreeOutBufferSpace(self):
        return self.outMaxQueueSize - self.outQueueSize
    
    
    def getErrorReason(self):
        return self.errorReason