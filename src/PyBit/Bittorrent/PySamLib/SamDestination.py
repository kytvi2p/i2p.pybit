"""
Copyright 2009  Blub

SamDestination, a collection of classes which represent sam destinations
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

from AsyncSocket import AsyncSocket
from SamSocket import SamTcpSocket, SamTcpListeningSocket
import SamMessages


class SamBaseDestination:
    def __init__(self, destId, asyncSocketManager, realSockStatus, log, ip, port,
                 sessionName, sessionType, sessionDirection, sessionOptions):
        self.destId = destId
        self.asyncSocketManager = asyncSocketManager
        self.realSockStatus = realSockStatus
        self.log = log
        
        #session - stats
        self.sessionName = sessionName
        self.sessionType = sessionType
        self.sessionDirection = sessionDirection
        self.sessionOptions = sessionOptions
        
        #session - state
        self.sessionEstablished = False
        self.sessionKey = None
        
        #socket
        self.sock = None
        self.sockNum = None
        self.ip = ip
        self.port = port
        self.connected = False
        self.inMessage = None
        self.inQueue = deque()
        self.outQueue = deque()
        
        self._connectRealSocket()
        
    
    ##internal functions - socket
    
    def _connectRealSocket(self):
        self.sock = AsyncSocket(self.asyncSocketManager)
        self.sock.connect((self.ip, self.port), 49152, 49152)
        self.sockNum = self.sock.fileno()
        self.realSockStatus.addConn(self.sockNum, self.destId)
        self.realSockStatus.setWantsToSend(True, self.sockNum)
        
        
    def _closeRealSocket(self):
        self.inMessage = None
        self.outQueue.clear()
        self.realSockStatus.removeConn(self.sockNum)
        self.connected = False
        self.sock.close()
        self.sock = None
        
        
    def _reconnectRealSocket(self):
        self._closeRealSocket()
        self._connectRealSocket()
        
    
    def _sendOverRealSocket(self, data):
        self.outQueue.append(data)
        if len(self.outQueue) == 1:
            #first message in buffer, add to sockets with send interest
            self.realSockStatus.setWantsToSend(True, self.sockNum)

        if self.log is not None:
            self.log.debug("Send Message: \"%s\"", data.split('\n')[0])
            
            
    ##internal functions - destinations
    
    def _establishedDestination(self):
        pass
    
    
    def _failDestination(self, reason):
        self.sessionKey = None
        self.sessionEstablished = False
        self._reconnectRealSocket()
        
        
    def _removeDestination(self):
        self._closeRealSocket()
        
    
    ##internal functions - messages
    
    def _handleCustomMessage(self, message):
        if self.log is not None:
            self.log.warn("Received unknown message from Sam bridge: \"%s\"", str(message))
            
            
    def _handleNameLookup(self, message):
        pass
    
    
    def _handleMessages(self, messages):
        for message in messages:
            messageType = message['msgType']
            messageParas = message['msgParas']
            
            if messageType=='HELLO REPLY':
                #handshake reply
                if messageParas['RESULT'].upper()=='OK' and messageParas['VERSION']=='2.0':
                    #send session create message
                    assert len(self.outQueue)==0, "just handshaked and stuff to send?!"
                    self._sendOverRealSocket(SamMessages.sessionCreateMessage(self.sessionType, self.sessionName, self.sessionDirection, self.sessionOptions))
                else:
                    #something borked
                    self._failDestination('Invalid HELLO REPLY: Result<%s> Version<%s>' % (messageParas['RESULT'], messageParas['VERSION']))
                
            elif messageType=='SESSION STATUS':
                #session established
                if not messageParas['RESULT'].upper()=='OK':
                    #urgh
                    self._failDestination('Failed to setup session: "%s"' % (messageParas['RESULT'],))
                else:
                    #ok, session is established
                    self.sessionEstablished = True
                    self._sendOverRealSocket('NAMING LOOKUP NAME=ME\n')
                    self._establishedDestination()
                    
            elif messageType=='NAMING REPLY':
                #reply to destination request
                if not messageParas['NAME'].upper() == 'ME': 
                    self._handleNameLookup(message)
                elif messageParas['RESULT'].upper() == 'OK':
                        self.sessionKey = messageParas['VALUE']
                    
            else:
                self._handleCustomMessage(message)
                    
            
    ##external functions - socket events
    
    def errorEvent(self):
        self._failDestination('Connection to SAM failed')
        
        
    def sendEvent(self):
        if not self.connected:
            #connected, send handshake as soon as possible
            self.connected = True
            self.realSockStatus.setWantsToRecv(True, self.sockNum)
            self.realSockStatus.setWantsToSend(False, self.sockNum)
            self._sendOverRealSocket("HELLO VERSION MIN=2.0 MAX=2.0\n")
            
            
        else:
            #already connected, send data
            assert len(self.outQueue) > 0, 'Empty outbuffer, but trying to send?!'
            
            while len(self.outQueue) > 0:
                #still something in the queue, try to send the next message
                data = self.outQueue.popleft()
                bytesSend = self.sock.send(data)
                if bytesSend < len(data):
                    #not all data send, push remaining data back into queue and abort loop
                    self.outQueue.appendleft(data[bytesSend:])
                    break
                    
            if len(self.outQueue) == 0:
                #managed to empty the queue, nothing to send anymore
                self.realSockStatus.setWantsToSend(False, self.sockNum)
                
                
    def recvEvent(self):
        data = self.sock.recv()
        dataLen = len(data)
        messages = []
        offset = 0
        
        #process data
        while not offset >= dataLen:
            #loop until all received data was processed
            if self.inMessage is None:
                ##there is no finished message that needs bulk data
                endOfMessage = data.find('\n', offset)
                if endOfMessage == -1:
                    #only the beginning of a message, store it in the inbound queue
                    self.inQueue.append(data[offset:])
                    offset = dataLen
                    
                else:
                    #the whole message or the ending
                    message = data[offset:endOfMessage]
                    offset = endOfMessage + 1
                    if len(self.inQueue) > 0:
                        #get the beginning of the message out of the queue
                        self.inQueue.append(message)
                        message = ''.join(self.inQueue)
                        self.inQueue.clear()
                    
                    #parse message
                    if self.log is not None:
                        self.log.debug("Got Message: \"%s\"", message)
                    message = SamMessages.parseMessage(message)
                        
                    #check if we need to wait for more data
                    if 'SIZE' in message['msgParas']:
                        message['Data'] = []
                        message['DataCurrentLen'] = 0
                        message['DataTargetLen'] = int(message['msgParas']['SIZE'])
                        self.inMessage = message
                    else:
                        messages.append(message)
            else:
                ##only missing a few bytes here ...
                assert len(self.inQueue) == 0, 'receiving data but stuff in the inqueue?!'
                missingBytes = self.inMessage['DataTargetLen'] - self.inMessage['DataCurrentLen']
                remainingBytes = dataLen - offset
                if remainingBytes >= missingBytes:
                    #got all
                    if self.log is not None:
                        self.log.debug("Got missing %i bytes for message", missingBytes)
                    self.inMessage['Data'].append(data[offset:offset+missingBytes])
                    self.inMessage['DataCurrentLen'] += missingBytes
                    assert self.inMessage['DataCurrentLen'] == self.inMessage['DataTargetLen'], 'message finished but too short?!'
                    offset += missingBytes
                    messages.append(self.inMessage)
                    self.inMessage = None
                
                else:
                    #still missing a bit
                    if self.log is not None:
                        self.log.debug("Got %i bytes for message but still missing %i bytes", remainingBytes, (missingBytes - remainingBytes))
                    self.inMessage['Data'].append(data[offset:])
                    self.inMessage['DataCurrentLen'] += remainingBytes
                    offset += remainingBytes        
        
        #handle messages
        self._handleMessages(messages)
        
        
    ##external functions - destination
    
    def getOwnDestination(self):
        return self.sessionKey
    
    
    def shutdown(self):
        self._removeDestination()
        
        
    ##external functions - changing settings
    
    def changeSessionAddress(self, ip=None, port=None, reconnect=False):
        if ip is not None:
            self.ip = ip
            
        if port is not None:
            self.port = port
            
        if reconnect:
            self._failDestination('SESSION_ADDR_CHANGE')
        
        
    def changeSessionName(self, sessionName, reconnect=False):
        self.sessionName = sessionName
        if reconnect:
            self._failDestination('SESSION_NAME_CHANGE')
        
       
    def changeSessionOption(self, option, value, reconnect=False):
        self.sessionOptions[option] = value
        if reconnect:
            self._failDestination('SESSION_OPTION_CHANGE')
        
        
    def removeSessionOption(self, option, reconnect=False):
        del self.sessionOptions[option]
        if reconnect:
            self._failDestination('SESSION_OPTION_CHANGE')
        
        
    def replaceSessionOptions(self, sessionOptions, reconnect=False):
        self.sessionOptions = sessionOptions
        if reconnect:
            self._failDestination('SESSION_OPTION_CHANGE')




class SamExtendedDestination(SamBaseDestination):
    def __init__(self, destId, asyncSocketManager, realSockStatus, log, ip, port,
                 sessionName, sessionType, sessionDirection, sessionOptions):
        
        #name lookup
        self.nameLookups = {}
        self.connIdToName = {}
        
        SamBaseDestination.__init__(self, destId, asyncSocketManager, realSockStatus, log, ip, port,
                                    sessionName, sessionType, sessionDirection, sessionOptions)
                                    
                                    
    ##internal functions - name lookup
    
    def _failDestination(self, reason):
        self.nameLookups.clear()
        self.connIdToName.clear()
        SamBaseDestination._failDestination(self, reason)
                                    
        
    ##internal functions - name lookup
    
    def _addNameLookupQuery(self, connId, name, func, funcArgs=[], funcKw={}):
        assert not connId in self.connIdToName, 'already running a lookup?!'
        self.connIdToName[connId] = name
        
        if name in self.nameLookups:
            #already running a lookup
            self.nameLookups[name][connId] = (func, funcArgs, funcKw)
        else:
            #start a new one
            self.nameLookups[name] = {connId:(func, funcArgs, funcKw)}
            self._sendOverRealSocket(SamMessages.nameLookup(name))
    
    
    def _removeNameLookupQuery(self, connId):
        if connId in self.connIdToName:
            #we are doing a name lookup for this conn
            name = self.connIdToName[connId]
            del self.connIdToName[connId]
            del self.nameLookups[name][connId]
            
            
    def _handleNameLookup(self, message):
        messageParas = message['msgParas']
        name = messageParas['NAME']
        if name in self.nameLookups:
            if messageParas['RESULT'].upper() == 'OK':
                #success
                success = True
                msg = messageParas['VALUE']
            else:
                #failure
                success = False
                msg = messageParas.get('MESSAGE', 'failure')
                
            for connId, func in self.nameLookups[name].iteritems():
                del self.connIdToName[connId]
                apply(func[0], func[1]+[success, msg], func[2])
                
            del self.nameLookups[name]
        
        
        
        
class SamRawDestination(SamBaseDestination):
    def __init__(self, destId, asyncSocketManager, realSockStatus, log, ip, port, sessionName, sessionType, sessionDirection, sessionOptions,
                 i2pSockStatus):
                    
        self.i2pSockStatus = i2pSockStatus
        self.i2pSockNum = self.i2pSockStatus.addConn(destId, 'raw', 'out')
        self.i2pSockInQueue = deque()
                    
        SamBaseDestination.__init__(self, destId, asyncSocketManager, realSockStatus, log, ip, port,
                                    sessionName, 'raw', sessionDirection, sessionOptions)
    
    
    ##internal functions - destinations
                                        
    def _establishedDestination(self):
        self.i2pSockStatus.setSendable(True, self.i2pSockNum)
        SamBaseDestination._establishedDestination(self)
    
    def _failDestination(self, reason):
        self.i2pSockStatus.setSendable(False, self.i2pSockNum)
        SamBaseDestination._failDestination(self, reason)
        
        
    def _removeDestination(self):
        self.i2pSockStatus.removeConn(self.i2pSockNum)
        SamBaseDestination._removeDestination(self)
    
    
    ##internal functions - messages
        
    def _handleCustomMessage(self, message):
        messageType = message['msgType']
        messageParas = message['msgParas']
        
        if messageType=='RAW RECEIVED':
            #received raw data
            if len(self.i2pSockInQueue) == 0:
                #first item in queue, add to recvable set
                self.i2pSockStatus.setRecvable(True, self.i2pSockNum)
                
            self.i2pSockStatus.append(''.join(message['Data']))
            
        else:
            if self.log is not None:
                self.log.warn("Received unknown message from Sam bridge: \"%s\"", str(message))
                
                
    ##external functions - send/recv
    
    def send(self, target, data):
        self._sendOverRealSocket(SamMessages.datagramSendMessage(target, data))
        return len(data)
    
    
    def recv(self, maxMessages, peekOnly):
        if maxMessages <= len(self.i2pSockInQueue):
            #just take the entire queue
            messages = list(self.i2pSockInQueue)
            if not peekOnly:
                self.i2pSockInQueue.clear()
                self.i2pSockStatus.setRecvable(False, self.i2pSockNum)
        else:
            #we only want a part of the queue
            messages = []
            if peekOnly:
                #keep messages in buffer
                count = 0
                for message in self.i2pSockInQueue:
                    #using for-loop because of poor slice-performance of deque
                    messages.append(message)
                    count += 1
                    if count == maxMessages:
                        break
            else:
                #purge messages out of buffer
                while len(messages) < maxMessages:
                    messages.append(self.i2pSockInQueue.popleft())
        return messages
    
    
    ##external functions - other
    
    def getI2PSocketId(self):
        return self.i2pSockNum
    
    


class SamUdpDestination(SamBaseDestination):
    def __init__(self, destId, asyncSocketManager, realSockStatus, log, ip, port, sessionName, sessionDirection, sessionOptions,
                 i2pSockStatus):
                    
        self.i2pSockStatus = i2pSockStatus
        self.i2pSockNum = self.i2pSockStatus.addConn(destId, 'udp', 'out')
        self.i2pSockInQueue = deque()
                    
        SamBaseDestination.__init__(self, destId, asyncSocketManager, realSockStatus, log, ip, port,
                                    sessionName, 'udp', sessionDirection, sessionOptions)
    
    
    ##internal functions - destinations
                                        
    def _establishedDestination(self):
        self.i2pSockStatus.setSendable(True, self.i2pSockNum)
        SamBaseDestination._establishedDestination(self)
        
    
    def _failDestination(self, reason):
        self.i2pSockStatus.setSendable(False, self.i2pSockNum)
        SamBaseDestination._failDestination(self, reason)
        
        
    def _removeDestination(self):
        self.i2pSockStatus.removeConn(self.i2pSockNum)
        SamBaseDestination._removeDestination(self)
    
    
    ##internal functions - messages
        
    def _handleCustomMessage(self, message):
        messageType = message['msgType']
        messageParas = message['msgParas']
        
        if messageType=='DATAGRAM RECEIVED':
            #received raw data
            if len(self.i2pSockInQueue) == 0:
                #first item in queue, add to recvable set
                self.i2pSockStatus.setRecvable(True, self.i2pSockNum)
                
            self.i2pSockInQueue.append(''.join(message['Data']))
            
        else:
            if self.log is not None:
                self.log.warn("Received unknown message from Sam bridge: \"%s\"", str(message))
                
                
    ##external functions - send/recv
    
    def send(self, target, data):
        self._sendOverRealSocket(SamMessages.datagramSendMessage(target, data))
        return len(data)
    
    
    def recv(self, maxMessages, peekOnly):
        if maxMessages <= len(self.i2pSockInQueue):
            #just take the entire queue
            messages = list(self.i2pSockInQueue)
            if not peekOnly:
                self.i2pSockInQueue.clear()
                self.i2pSockStatus.setRecvable(False, self.i2pSockNum)
        else:
            #we only want a part of the queue
            messages = []
            if peekOnly:
                #keep messages in buffer
                count = 0
                for message in self.i2pSockInQueue:
                    #using for-loop because of poor slice-performance of deque
                    messages.append(message)
                    count += 1
                    if count == maxMessages:
                        break
            else:
                #purge messages out of buffer
                while len(messages) < maxMessages:
                    messages.append(self.i2pSockInQueue.popleft())
        return messages
    
    
    ##external functions - other
    
    def getI2PSocketId(self):
        return self.i2pSockNum
    



class SamTcpDestination(SamExtendedDestination):
    def __init__(self, destId, asyncSocketManager, realSockStatus, log, ip, port, sessionName, sessionDirection, sessionOptions,
                 i2pSockStatus, defaultOutMaxQueueSize, defaultInMaxQueueSize, defaultInRecvLimitThreshold):
        
        #i2p socket
        self.i2pSockStatus = i2pSockStatus
        self.i2pSockets = {}
        self.i2pListeningSocket = None
        self.defaultOutMaxQueueSize = defaultOutMaxQueueSize
        self.defaultInMaxQueueSize = defaultInMaxQueueSize
        self.defaultInRecvLimitThreshold = defaultInRecvLimitThreshold
        
        #sam
        self.nextSamOutId = 1
        self.nextSamInId = -1
        
        #mapper
        self.connIdToSamId = {}     #mapper from conn id to sam id for all active conns
        self.samIdToConnId = {}     #mapper from sam id to conn id for all active conns
        
        #other
        self.failedSockets = set()  #set of conn ids which are not active, meaning they already failed but were not removed
        self.waitingSockets = set() #set of conn ids of all outgoing conns which wait for session establishement to connect
                    
        SamExtendedDestination.__init__(self, destId, asyncSocketManager, realSockStatus, log, ip, port,
                                        sessionName, 'tcp', sessionDirection, sessionOptions)
    
    
    ##internal functions - destinations
                                        
    def _establishedDestination(self):
        #send connect messages for all sockets which were created in the meantime
        for connId in self.waitingSockets:
            self._connectI2PSocket(connId, self.i2pSockets[connId])
        self.waitingSockets.clear()
        SamExtendedDestination._establishedDestination(self)
            
    
    def _failDestination(self, reason):
        #fail sockets
        for connId in self.i2pSockets.keys():
            if connId not in self.failedSockets:
                self.i2pSockets[connId].errorEvent('SESSION_FAILED')
                
        assert len(self.connIdToSamId)==0 and len(self.samIdToConnId)==0, 'failed all conns but active conns left?!'
        assert len(self.waitingSockets)==0, 'failed but still waiting?!'
            
        #clear listening socket if any
        if self.i2pListeningSocket is not None:
            self.i2pListeningSocket.clear()
            
        #reset status
        self.nextSamOutId = 1
        self.nextSamInId = -1
        
        SamExtendedDestination._failDestination(self, reason)
        
        
    def _removeDestination(self):
        #fail sockets
        for connId in self.i2pSockets.keys():
            if not connId in self.failedSockets:
                self.i2pSockets[connId].errorEvent('SESSION_CLOSED')
        
        assert len(self.connIdToSamId)==0 and len(self.samIdToConnId)==0, 'failed all conns but active conns left?!'
        assert len(self.waitingSockets)==0, 'failed but still waiting?!'
        
        #remove sockets
        for i2pSocket in self.i2pSockets.values():
            i2pSocket.close(force=True)
            
        #listening socket
        if self.i2pListeningSocket is not None:
            self.i2pSockStatus.removeConn(self.i2pListeningSocket.fileno())
            self.i2pListeningSocket = None
            
        SamExtendedDestination._removeDestination(self)
        
        
    ##internal functions - sockets
    
    def _addOutgoingI2PSocket(self, remoteDest, inMaxQueueSize=None, outMaxQueueSize=None, inRecvLimitThreshold=None):
        #set defaults
        if inMaxQueueSize is None:
            inMaxQueueSize = self.defaultInMaxQueueSize
            
        if outMaxQueueSize is None:
            outMaxQueueSize = self.defaultOutMaxQueueSize
            
        if inRecvLimitThreshold is None:
            inRecvLimitThreshold = self.defaultInRecvLimitThreshold
            
        #add to status obj
        connId = self.i2pSockStatus.addConn(self.destId, 'tcpOut', 'out')
        
        #create socket object
        conn = SamTcpSocket(self._sendOverRealSocket, self._failI2PSocket, self._removeI2PSocket, self.i2pSockStatus, connId, None, 'out', remoteDest, 
                            inMaxQueueSize, outMaxQueueSize, inRecvLimitThreshold)
        self.i2pSockets[connId] = conn
        
        #connect
        if self.sessionEstablished:
            self._connectI2PSocket(connId, conn)
        else:
            self.waitingSockets.add(connId)
            
        return connId
            
    
    def _addIncommingI2PSocket(self, samId, remoteDest):
        #add to status obj
        connId = self.i2pSockStatus.addConn(self.destId, 'tcpIn', 'in')
        
        #increment samId counter
        assert self.nextSamInId >= samId , 'Wrong assumption about sam id?!'
        self.nextSamInId = samId - 1
        
        #add to mapper
        self.connIdToSamId[connId] = samId
        self.samIdToConnId[samId] = connId
        
        #create socket object
        conn = SamTcpSocket(self._sendOverRealSocket, self._failI2PSocket, self._removeI2PSocket, self.i2pSockStatus, connId, samId, 'in', remoteDest, 
                            self.defaultInMaxQueueSize, self.defaultOutMaxQueueSize, self.defaultInRecvLimitThreshold)
        self.i2pSockets[connId] = conn
        
        #connect event
        conn.connectEvent()
        
        #add to listening socket
        if self.i2pListeningSocket is not None:
            self.i2pListeningSocket.acceptEvent(connId, remoteDest)
            
            
    def _allocateSamId(self, connId):
        samId = self.nextSamOutId
        self.nextSamOutId += 1
        
        #add to mapper
        self.connIdToSamId[connId] = samId
        self.samIdToConnId[samId] = connId
        return samId
            
            
    def _connectI2PSocket(self, connId, i2pSocket):
        remoteDest = i2pSocket.getRemoteDestination()
        if len(remoteDest) == 516 and remoteDest.endswith('AAAA'):
            #full i2p destination
            samId = self._allocateSamId(connId)
            i2pSocket.connect(remoteDest, samId)
            
        else:
            #not a real destination but some kind of name
            self._addNameLookupQuery(connId, remoteDest, self._finishedNameLookup, funcArgs=[connId])
            
            
    def _finishedNameLookup(self, connId, success, msg):
        if success:
            samId = self._allocateSamId(connId)
            self.i2pSockets[connId].connect(msg, samId)
        else:
            self.i2pSockets[connId].errorEvent('FAILED_NAME_LOOKUP')
            
    
    def _failI2PSocket(self, connId):
        "called when a conn failed, either an already connected one or a connecting one"
        i2pSocket = self.i2pSockets[connId]
        samId = self.connIdToSamId.get(connId)
        
        if samId is None:
            #outgoing conn with name query, remove
            self._removeNameLookupQuery(connId)
        
        else:
            #active conn, remove from id mapper
            del self.connIdToSamId[connId]
            del self.samIdToConnId[samId]
        
        #set changes
        self.waitingSockets.discard(connId)
        self.failedSockets.add(connId)
        
    
    def _removeI2PSocket(self, connId):
        "called when close() was called for a socket"
        #remove from set
        self.failedSockets.remove(connId)
        
        #remove from socket dict
        del self.i2pSockets[connId]
        
        #remove from status obj
        self.i2pSockStatus.removeConn(connId)
    
    
    ##internal functions - messages
        
    def _handleCustomMessage(self, message):
        messageType = message['msgType']
        messageParas = message['msgParas']
        
        if messageType=='STREAM STATUS':
            #a outgoing sam tcp-socket connected ... or failed
            samId = int(messageParas['ID'])
            connId = self.samIdToConnId.get(samId)
            
            if connId is not None:
                #i2p socket still exists
                i2pSocket = self.i2pSockets[connId]
                if messageParas['RESULT'].upper() == 'OK':
                    #socket connected
                    i2pSocket.connectEvent()
                else:
                    #failed
                    i2pSocket.errorEvent(messageParas['RESULT'])
                    
            
        elif messageType=='STREAM CONNECTED':
            #got a new incomming tcp-like connection
            samId = int(messageParas['ID'])
            self._addIncommingI2PSocket(samId, messageParas['DESTINATION'])
            
            
        elif messageType=='STREAM SEND':
            #status info about a previous STREAM SEND command
            
            samId = int(messageParas['ID'])
            connId = self.samIdToConnId.get(samId)
                
            if connId is not None:
                #socket still exists
                i2pSocket = self.i2pSockets[connId]
                if messageParas['RESULT'].upper() == 'OK':
                    #data was send
                    i2pSocket.sendSucceededEvent()
                else:
                    #for some reason, the send failed - probably a bug, but a bug in this lib or in sam?
                    i2pSocket.sendFailedEvent()
                    
                if messageParas['STATE'].upper() == 'READY':
                    #the buffer of the sam bridge is not full, allowed to send more
                    i2pSocket.sendEvent()
                    
        
        elif messageType=='STREAM READY_TO_SEND':
            samId = int(messageParas['ID'])
            connId = self.samIdToConnId.get(samId)
                
            if connId is not None:
                #socket still exists
                self.i2pSockets[connId].sendEvent()
                
        
        elif messageType=='STREAM CLOSED':
            samId = int(messageParas['ID'])
            connId = self.samIdToConnId.get(samId)
                
            if connId is not None:
                #socket still exists
                if messageParas['RESULT'].upper() == 'OK':
                    #OK isn't a good error reason ...
                    messageParas['RESULT'] = 'CLOSED_BY_PEER'
                    
                self.i2pSockets[connId].errorEvent(messageParas['RESULT'])
                
        
        elif messageType=='STREAM RECEIVED':
            samId = int(messageParas['ID'])
            connId = self.samIdToConnId.get(samId, None)
                
            if connId is not None:
                #socket still exists
                self.i2pSockets[connId].recvEvent(''.join(message['Data']))
                
        else:
            if self.log is not None:
                self.log.error('Got unknown message "%s" with the following paras:\n%s', messageType, '\n'.join(tup[0]+': '+tup[1] for tup in messageParas.iteritems()))
        
        
    ##external functions - sockets - normal
    
    def connect(self, remoteDest, inMaxQueueSize=None, outMaxQueueSize=None, inRecvLimitThreshold=None):
        return self._addOutgoingI2PSocket(remoteDest, inMaxQueueSize, outMaxQueueSize, inRecvLimitThreshold)
    
    
    def send(self, connId, data):
        return self.i2pSockets[connId].send(data)
    
    
    def recv(self, connId, max, peekOnly):
        return self.i2pSockets[connId].recv(max, peekOnly)
    
    
    def close(self, connId, force):
        if connId in self.i2pSockets:
            self.i2pSockets[connId].close(force)
        
        
    ##external functions - sockets - listening
        
    def startListening(self, addOld):
        assert self.i2pListeningSocket is None,'there is already one?!'
        
        if addOld:
            existingConns = [samId for samId in self.samIdToConnId.itervalues() if samId < 0]
        else:
            existingConns = None
        
        connId = self.i2pSockStatus.addConn(self.destId, 'tcpListen', 'out')
        self.i2pListeningSocket = SamTcpListeningSocket(self.i2pSockStatus, connId, existingConns)
        return connId
    
    
    def accept(self, max):
        return self.i2pListeningSocket.accept(max)
    
    
    def stopListening(self, connId):
        assert self.i2pListeningSocket.fileno() == connId, 'connId doesn\'t match id of listening socket!'
        self.i2pSockStatus.removeConn(connId)
        self.i2pListeningSocket = None
        
        
    ##external functions - change settings
    
    def changeDefaultQueueSize(self, defaultInMaxQueueSize=None, defaultOutMaxQueueSize=None):
        if defaultInMaxQueueSize is not None:
            self.defaultInMaxQueueSize = defaultInMaxQueueSize
        if defaultOutMaxQueueSize is not None:
            self.defaultOutMaxQueueSize = defaultOutMaxQueueSize
            
    
    def changeDefaultInRecvLimitThreshold(self, defaultInRecvLimitThreshold):
        self.defaultInRecvLimitThreshold = self.defaultInRecvLimitThreshold
        
        
    ##external functions - get info
    
    def getI2PSocketRemoteDestination(self, connId):
        return self.i2pSockets[connId].getRemoteDestination()
    
    
    def getI2PSocketUsedInBufferSpace(self, connId):
        return self.i2pSockets[connId].getUsedInBufferSpace()
    
    
    def getI2PSocketFreeOutBufferSpace(self, connId):
        return self.i2pSockets[connId].getFreeOutBufferSpace()
    
    
    def getI2PSocketErrorReason(self, connId):
        return self.i2pSockets[connId].getErrorReason()