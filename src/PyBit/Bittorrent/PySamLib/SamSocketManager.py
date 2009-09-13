"""
Copyright 2008  Blub

SamSocketManager, a class which handles the communication with SAM-bridges.
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
from time import sleep, time
import logging
import threading

from AsyncSocketManager import AsyncSocketManager
from Utilities import getTraceback
import SamMessages

class SamSocketManager:
    def __init__(self, log=None, asmLog=None):
        self.log = log
        if type(self.log)==str:
            self.log = logging.getLogger(self.log)
            
        if type(asmLog)==str:
            asmLog = logging.getLogger(asmLog)
        
        self.sockManager = AsyncSocketManager(log=asmLog) #handler for real sockets
        self.realSockets = {} #all real sockets, realSocketNumber => socketInfo mapping
        self.allRealSocks = set() #numbers of all real sockets
        self.realSocksWithRecvInterest = set() #numbers of all real sockets which we want to receive data from
        self.realSocksWithSendInterest = set() #numbers of all real sockets which we want to use to send data
        
        self.samDests = {} #destination num => info set, for all sam destinations
        self.samSockets = {}
        
        self.uniqueDestId = 1
        self.uniqueConnOutId = 1
        self.uniqueConnInId = -1       
        
        self.allSamSockets = set()
        self.recvableSamSockets = set()
        self.sendableSamSockets = set()
        self.erroredSamSockets = set()
        
        self.shouldStop = True
        self.lock = threading.Lock() #the main lock
        self.socketActEvent = threading.Event()
        self.thread = None
        
        
    ##THREAD##
    
    def _start(self):
        assert self.shouldStop==True, 'not stopped?! out of sync?'
        self.shouldStop = False
        if self.thread is None:
            #only start a thread if the old one already died
            self.thread = threading.Thread(target=self.run)
            self.thread.start()
            if self.log is not None:
                self.log.debug("Starting thread")
                
            
    def _stop(self):
        assert self.shouldStop==False, 'stopped?! out of sync?'
        assert self.thread is not None, 'no thread but stopping?!'
        
        self.shouldStop = True
        self.socketActEvent.set()
        if self.log is not None:
            self.log.debug("Stopping thread")
        
        #remove all failed sockets which are left 
        #(any still existing socket MUST be failed, else there is a bug somewhere)
        #for samSocketId in self.samSockets.keys():
        #    self._closeSamTcpSocket(samSocketId)        
        
        #for debugging
        assert len(self.samDests)==0, 'stopping thread but sam destinations left?!'
        #assert len(self.samSockets)==0, 'stopping thread but sam sockets left?!'
        #assert len(self.recvableSamSockets)==0, 'stopping thread but still recvable sam sockets left?!'
        assert len(self.sendableSamSockets)==0, 'stopping thread but still sendable sam socket left?!'
        #assert len(self.erroredSamSockets)==0, 'stopping thread but still errored sam sockets left?!'
        
        
    ##SOCKET##
    
    def _addRealSocket(self, ip, port, destNum, checkThread=True):
        realSocketNum = self.sockManager.connect((ip, port), 49152, 49152)
        self.realSockets[realSocketNum] = {'connected':False,
                                           'ip':ip,
                                           'port':port,
                                           'destNum':destNum,
                                           'inMessage':None,
                                           'inQueue':deque(),
                                           'outQueue':deque()}
        self.allRealSocks.add(realSocketNum)
        self.realSocksWithSendInterest.add(realSocketNum)
        
        if checkThread and len(self.allRealSocks)==1:
            #first connection, start thread
            self._start()
            
        return realSocketNum
    
    
    def _closeSocket(self, realSocketNum, checkThread=True):
        self.sockManager.close(realSocketNum)
        realSockSet = self.realSockets[realSocketNum]
        
        #remove from sets
        if realSockSet['connected']==False or len(realSockSet['outQueue']) > 0:
            self.realSocksWithSendInterest.remove(realSocketNum)
        if realSockSet['connected']:
            self.realSocksWithRecvInterest.remove(realSocketNum)
        self.allRealSocks.remove(realSocketNum)
        
        del self.realSockets[realSocketNum]  
        if checkThread and len(self.allRealSocks)==0:
            #just closed the last connection
            self._stop()
            
        
    def _reconnectSocket(self, realSocketNum):
        ip = self.realSockets[realSocketNum]['ip']
        port = self.realSockets[realSocketNum]['port']
        destNum = self.realSockets[realSocketNum]['destNum']
        
        self._closeSocket(realSocketNum, checkThread=False)
        realSocketNum = self._addRealSocket(ip, port, destNum, checkThread=False)
        return realSocketNum
    
    
    def _changeSocketConnectAddress(self, realSocketNum, ip, port):
        if ip is not None:
            self.realSockets[realSocketNum]['ip'] = ip
        if port is not None:
            self.realSockets[realSocketNum]['port'] = port
    
    
    def _sendOverRealSocket(self, realSockNum, data):
        #just add the message to the outgoing queue of the socket
        realSocket = self.realSockets[realSockNum]
        realSocket['outQueue'].append(data)
        if len(realSocket['outQueue'])==1:
            #first message in buffer, add to set of sockets with send interest
            self.realSocksWithSendInterest.add(realSockNum)
        if self.log is not None:
            self.log.debug("Send Message: \"%s\"", data.split('\n')[0])
    
    
    ##DESTINATION##
    
    def _addDestination(self, ip, port, destName, type, direction, sessionOptions, defaultOutMaxQueueSize, defaultInMaxQueueSize, defaultInRecvLimitThreshold):
        realSocketNum = self._addRealSocket(ip, port, self.uniqueDestId)        
        
        result = {}
        #remember session details
        if type=='udp' or type=='raw':
            #simple udp-like socket, only one sam socket for each destination
            self.samDests[self.uniqueDestId] = {'realSocket':realSocketNum,
                                                'samSocket':self.uniqueConnOutId,
                                                'destName':destName,
                                                'destKey':None,
                                                'sessionEstablished':False,
                                                'sessionType':type,
                                                'sessionDirection':direction,
                                                'sessionOptions':sessionOptions}
                                                
            
            self.samSockets[self.uniqueConnOutId] = {'destNum':self.uniqueDestId,
                                                     'inQueue':deque(),
                                                     'type':type}
            
            self.allSamSockets.add(self.uniqueConnOutId)
            
            result = (self.uniqueDestId, self.uniqueConnOutId)
            self.uniqueDestId += 1
            self.uniqueConnOutId += 1        
            
        elif type=='tcp':
            #tcp-like
            self.samDests[self.uniqueDestId] = {'realSocket':realSocketNum,
                                                'samOutSockets':{},
                                                'samInSockets':{},
                                                'samListenSocket':None,
                                                'samInId':-1,
                                                'samOutId':1,
                                                'destName':destName,
                                                'destKey':None,
                                                'sessionEstablished':False,
                                                'sessionType':type,
                                                'sessionDirection':direction,
                                                'sessionOptions':sessionOptions,
                                                'defaultOutMaxQueueSize':defaultOutMaxQueueSize,
                                                'defaultInMaxQueueSize':defaultInMaxQueueSize,
                                                'defaultInRecvLimitThreshold':defaultInRecvLimitThreshold}
            result = self.uniqueDestId
            self.uniqueDestId += 1
        return result
    
            
    def _failDestination(self, destNum, reason):
        destSet = self.samDests[destNum]
        if destSet['sessionType']=='udp' or destSet['sessionType']=='raw':
            #clear outbound buffer of samSocket, remove from sendable set
            samSockNum = destSet['samSocket']
            if destSet['sessionEstablished']==True:
                self.sendableSamSockets.remove(samSockNum)
            
            #change session status
            destSet['destKey'] = None
            destSet['sessionEstablished'] = False
            
            #reconnect real Socket
            destSet['realSocket'] = self._reconnectSocket(destSet['realSocket'])
        
        elif destSet['sessionType']=='tcp':
            #fail each sam tcp-socket
            for samSocketId in destSet['samOutSockets'].values():
                self._failSamTcpSocket(samSocketId, errorReason='SESSION_FAILED')
            
            for samSocketId in destSet['samInSockets'].values():
                self._failSamTcpSocket(samSocketId, errorReason='SESSION_FAILED')
                
            #remove queued incomming conns from listening socket
            if destSet['samListenSocket'] is not None:
                self.samSockets[destSet['samListenSocket']]['newSamInSockets'].clear()
            
            #change session status
            destSet['destKey'] = None
            destSet['sessionEstablished'] = False
            destSet['samInId'] = -1
            destSet['samOutId'] = 1
            
            #reconnect real Socket
            destSet['realSocket'] = self._reconnectSocket(destSet['realSocket'])
            
    
    def _removeDestination(self, destNum):
        destSet = self.samDests[destNum]
        if destSet['sessionType']=='udp' or destSet['sessionType']=='raw':
            #remove samSocket from sets
            samSockNum = destSet['samSocket']
            if destSet['sessionEstablished']==True:
                self.sendableSamSockets.remove(samSockNum)    
                
            if len(self.samSockets[samSockNum]['inQueue']) > 0:
                self.recvableSamSockets.remove(samSockNum)
                
            self.allSamSockets.remove(samSockNum)
            
            #remove sam socket
            del self.samSockets[samSockNum]
            
            #remove dest info
            del self.samDests[destNum]
            
            #close real socket
            self._closeSocket(destSet['realSocket'])
        
        elif destSet['sessionType']=='tcp':
            #close each sam tcp-socket
            for samSocketId in destSet['samOutSockets'].values():
                self._failSamTcpSocket(samSocketId, errorReason='SESSION_CLOSED')
            
            for samSocketId in destSet['samInSockets'].values():
                self._failSamTcpSocket(samSocketId, errorReason='SESSION_CLOSED')
                
            #remove listening socket
            if destSet['samListenSocket'] is not None:
                self._removeListeningSamTcpSocket(destNum)
                
            #remove dest info
            del self.samDests[destNum]
            
            #close real socket
            self._closeSocket(destSet['realSocket'])
            
    
    def _removeAllDestinations(self):
        for destNum in self.samDests.keys():
            self._removeDestination(destNum)
            
          
    def _changeDefaultQueueSize(self, destSet, defaultInMaxQueueSize=None, defaultOutMaxQueueSize=None):        
        if defaultInMaxQueueSize is not None:
            destSet['defaultInMaxQueueSize'] = defaultInMaxQueueSize
            if destSet['defaultInRecvLimitThreshold'] > destSet['defaultInMaxQueueSize']:
                #this cannot work, set it to the highest sensible threshold
                destSet['defaultInRecvLimitThreshold'] = destSet['defaultInMaxQueueSize']
            
        if defaultOutMaxQueueSize is not None:
            destSet['defaultOutMaxQueueSize'] = defaultOutMaxQueueSize
            
            
    def _changeDefaultInRecvLimitThreshold(self, destSet, defaultInRecvLimitThreshold):
        destSet['defaultInRecvLimitThreshold'] = defaultInRecvLimitThreshold
        
        
    def _changeSamBridgeAddress(self, destNum, ip, port, reconnect):
        self._changeSocketConnectAddress(self.samDests[destNum]['realSocket'], ip, port)
        if reconnect:
            self._failDestination(destNum, 'sam bridge address changed')
            
            
    def _changeDestinationName(self, destNum, destName, reconnect):
        self.samDests[destNum]['destName'] = destName
        if reconnect:
            self._failDestination(destNum, 'destination name changed')
        
            
    def _changeSessionOption(self, destNum, option, value, reconnect):
        destSet = self.samDests[destNum]
        destSet['sessionOptions'][option] = value
        if reconnect:
            self._failDestination(destNum, 'session options changed')
            
            
    def _removeSessionOption(self, destNum, option, reconnect):
        destSet = self.samDests[destNum]
        if option in destSet['sessionOptions']:
            del destSet['sessionOptions'][option]
            if reconnect:
                self._failDestination(destNum, 'session options changed')
                
                
    def _replaceSessionOptions(self, destNum, sessionOptions, reconnect):
        destSet = self.samDests[destNum]
        destSet['sessionOptions'] = sessionOptions
        if reconnect:
            self._failDestination(destNum, 'session options changed')
            
    
    ##SAM TCP SOCKET##
    
    def _addOutgoingSamTcpSocket(self, targetDest, destNum, inMaxQueueSize, outMaxQueueSize, inRecvLimitThreshold):
        destSet = self.samDests[destNum]
        samId = destSet['samOutId']
        
        #create socket data structure
        self.samSockets[self.uniqueConnOutId] = {'destNum':destNum,
                                                 'samId':samId,
                                                 'connected':False,
                                                 'waitingForClose':False,
                                                 'errorReason':None,
                                                 'inQueue':deque(),
                                                 'inQueueSize':0,
                                                 'inMaxQueueSize':inMaxQueueSize,
                                                 'inBytesReceived':0,
                                                 'inRecvLimit':0,
                                                 'inRecvLimitThreshold':inRecvLimitThreshold,
                                                 'outMessage':None,
                                                 'outQueue':deque(),
                                                 'outQueueSize':0,
                                                 'outMaxQueueSize':outMaxQueueSize,
                                                 'outSendable':False,
                                                 'remoteDest':targetDest,
                                                 'type':'tcpOut'}

                                                
        #add it to the destination info
        destSet['samOutSockets'][samId] = self.uniqueConnOutId
        
        #add to all set
        self.allSamSockets.add(self.uniqueConnOutId)
                
        #send the sam bridge a message, if already connected
        if destSet['sessionEstablished']:
            self._sendOverRealSocket(destSet['realSocket'] ,SamMessages.streamConnectMessage(destSet['samOutId'], targetDest))
            
        #increment Ids
        destSet['samOutId'] += 1
        self.uniqueConnOutId += 1
        
        return self.uniqueConnOutId - 1
        
        
    def _addIncommingSamTcpSocket(self, samId, sourceDest, destNum):
        destSet = self.samDests[destNum]
        #debug, FIXME
        if not samId<=destSet['samInId']:
            if self.log is not None:
                self.log.error('Bug: Expected samId <=%d but got samId \"%d\"!', destSet['samInId'], samId)
        assert samId<=destSet['samInId'], 'assumptions about samId of incomming tcp-streams wrong?!'

        #create socket data structure
        self.samSockets[self.uniqueConnInId] = {'destNum':destNum,
                                                'samId':samId,
                                                'connected':True,
                                                'waitingForClose':False,
                                                'errorReason':None,
                                                'inQueue':deque(),
                                                'inQueueSize':0,
                                                'inMaxQueueSize':destSet['defaultInMaxQueueSize'],
                                                'inBytesReceived':0,
                                                'inRecvLimit':destSet['defaultInMaxQueueSize'],
                                                'inRecvLimitThreshold':destSet['defaultInRecvLimitThreshold'],
                                                'outMessage':None,
                                                'outQueue':deque(),
                                                'outQueueSize':0,
                                                'outMaxQueueSize':destSet['defaultOutMaxQueueSize'],
                                                'outSendable':True,
                                                'remoteDest':sourceDest,
                                                'type':'tcpIn'}
                                                
        #add it to the destination info
        destSet['samInSockets'][samId] = self.uniqueConnInId
        
        #notify the listening socket, if one exists
        if destSet['samListenSocket'] is not None:
            listenSamSocketId = destSet['samListenSocket']
            listenSamSocket = self.samSockets[listenSamSocketId]
            listenSamSocket['newSamInSockets'].append(self.uniqueConnInId)
            if len(listenSamSocket['newSamInSockets'])==1:
                #first, add to listen socket to recvable list
                self.recvableSamSockets.add(listenSamSocketId)
            
            
                
        #send the sam bridge a new receive limit
        self._sendOverRealSocket(destSet['realSocket'], SamMessages.streamReceiveLimitMessage(samId, self.samSockets[self.uniqueConnInId]['inRecvLimit']))
            
        #add to sets
        self.sendableSamSockets.add(self.uniqueConnInId)
        self.allSamSockets.add(self.uniqueConnInId)
        self.socketActEvent.set()
        
        #decrement Ids
        destSet['samInId'] = samId-1
        self.uniqueConnInId -= 1
        
    
    def _addListeningSamTcpSocket(self, destNum, addOld):
        destSet = self.samDests[destNum]
        assert destSet['samListenSocket'] is None, 'listening socket already exists!'
        
        #create socket data structure
        self.samSockets[self.uniqueConnOutId] = {'destNum':destNum,
                                                 'newSamInSockets':deque(),
                                                 'type':'tcpListen'}
        
        #add it to the dest info
        destSet['samListenSocket'] = self.uniqueConnOutId
        
        #add it to the all set
        self.allSamSockets.add(self.uniqueConnOutId)
        
        #add already existing incomming conns
        if addOld:
            if len(destSet['samInSockets']) > 0:
                self.recvableSamSockets.add(self.uniqueConnOutId)
                self.socketActEvent.set()
                for samSocketId in destSet['samInSockets'].itervalues():
                    self.samSockets[self.uniqueConnOutId]['newSamInSockets'].append(samSocketId)   
        
        #increment Id
        self.uniqueConnOutId += 1
        return self.uniqueConnOutId - 1
    
        
    def _removeListeningSamTcpSocket(self, destNum):
        destSet = self.samDests[destNum]
        assert destSet['samListenSocket'] is not None, 'no listening socket but removing one?!'
        samSocketId = destSet['samListenSocket']
        samSocket = self.samSockets[samSocketId]
        
        #remove from recv set
        if len(samSocket['newSamInSockets']) > 0:
            self.recvableSamSockets.remove(samSocketId)
            samSocket['newSamInSockets'].clear()
            
        #remove from all set
        self.allSamSockets.remove(samSocketId)
            
        #remove from dest info
        destSet['samListenSocket'] = None
        
        
        #remove socket info
        del self.samSockets[samSocketId]
        
        
    def _queueDataForSamTcpSocket(self, destSet, samSocket, samSocketId, data):
        allowedBytes = samSocket['outMaxQueueSize'] - samSocket['outQueueSize']
        bytesToSend = len(data)
        
        #put data into queue
        if allowedBytes >= bytesToSend:
            #put everything into the queue
            samSocket['outQueue'].append(data)
            bytesSend = bytesToSend
        else:
            #too large, only take a part
            samSocket['outQueue'].append(data[:allowedBytes])
            bytesSend = allowedBytes
        
        samSocket['outQueueSize'] += bytesSend
        
        #check if queue full
        if samSocket['outQueueSize'] >= samSocket['outMaxQueueSize']:
            #buffer filled
            self.sendableSamSockets.remove(samSocketId)
            
        #check if sendable
        if samSocket['outSendable']:
            self._sendDataFromSamTcpSocket(samSocketId)
        return bytesSend
    
    
    def _pushBackDataFromSamTcpSocket(samSocket, samSocketId, data):
        samSocket['outQueue'].appendleft(data)
        samSocket['outQueueSize'] += len(data)
        
        if (not samSocket['waitingForClose']) and \
           samSocket['outQueueSize'] >= samSocket['outMaxQueueSize'] and \
           (samSocket['outQueueSize'] - len(data)) < samSocket['outMaxQueueSize']:
            #buffer was not full and is now full again
            self.sendableSamSockets.remove(samSocketId)
            
        
    def _sendDataFromSamTcpSocket(self, samSocketId):
        samSocket = self.samSockets[samSocketId]
        destSet = self.samDests[samSocket['destNum']]
        
        if samSocket['outQueueSize'] <= 32768:
            #fits into a single message
            data = ''.join(samSocket['outQueue'])
            dataSize = len(data)
            samSocket['outQueue'].clear()
            samSocket['outQueueSize'] = 0
        else:
            #too much data for a single message
            data = []
            dataSize = 0
            while dataSize < 32768:
                #add chunks until the limit is reached
                dataChunk = samSocket['outQueue'].popleft()
                dataChunkLen = len(dataChunk)
                if dataSize + dataChunkLen < 32768:
                    #take entire chunk
                    data.append(dataChunk)
                    dataSize += dataChunkLen
                    samSocket['outQueueSize'] -= dataChunkLen
                else:
                    #only take a part of the chunk
                    useableDataChunkLen = 32768 - dataSize
                    data.append(dataChunk[:useableDataChunkLen])
                    samSocket['outQueue'].appendleft(dataChunk[useableDataChunkLen:])
                    samSocket['outQueueSize'] -= useableDataChunkLen
                    dataSize += useableDataChunkLen
            data = ''.join(data)
            
        if (not samSocket['waitingForClose']) and \
           samSocket['outQueueSize'] < samSocket['outMaxQueueSize'] and \
           (samSocket['outQueueSize'] + dataSize) >= samSocket['outMaxQueueSize']:
            #buffer was full and is not full anymore
            self.sendableSamSockets.add(samSocketId)
            self.socketActEvent.set()
            
        #send data to the sam bridge
        self._sendOverRealSocket(destSet['realSocket'], SamMessages.streamSendMessage(samSocket['samId'], data))   
        
        #remember data, in case sam rejects it
        samSocket['outMessage'] = data
        
        #don't send anything until the sam bridge send us its status
        samSocket['outSendable'] = False
        
        
    def _recvQueuedDataFromSamTcpSocket(self, destSet, samSocket, samSocketId, maxBytes, peekOnly):
        availableBytes = samSocket['inQueueSize']
        
        if maxBytes==-1 or availableBytes <= maxBytes:
            #take everything available
            data = ''.join(samSocket['inQueue'])
            if not peekOnly:
                samSocket['inQueue'].clear()
                samSocket['inQueueSize'] = 0
                self.recvableSamSockets.remove(samSocketId)
        else:
            #too much, only take a part
            data = []
            dataSize = 0
            count = 0
            while dataSize < maxBytes:
                #add chunks until the limit is reached
                if peekOnly:
                    dataChunk = samSocket['inQueue'][count]
                    count += 1
                else:
                    dataChunk = samSocket['inQueue'].popleft()
                dataChunkLen = len(dataChunk)
                if dataSize + dataChunkLen < maxBytes:
                    #take entire chunk
                    data.append(dataChunk)
                    dataSize += dataChunkLen
                    if not peekOnly:
                        samSocket['inQueueSize'] -= dataChunkLen
                else:
                    #only take a part of the chunk
                    useableDataChunkLen = maxBytes - dataSize
                    data.append(dataChunk[:useableDataChunkLen])
                    dataSize += useableDataChunkLen
                    if not peekOnly:
                        samSocket['inQueue'].appendleft(dataChunk[useableDataChunkLen:])
                        samSocket['inQueueSize'] -= useableDataChunkLen
                    
            data = ''.join(data)
        
        allowedBytes = samSocket['inMaxQueueSize'] - samSocket['inQueueSize']
        if allowedBytes > 0:
            #free buffer space above threshold
            recvLimit = allowedBytes + samSocket['inBytesReceived']
            if destSet['sessionEstablished'] and samSocket['samId'] is not None and recvLimit > (samSocket['inRecvLimitThreshold'] + samSocket['inRecvLimit']):
                #new recv limit, notify sam bridge, if connected
                samSocket['inRecvLimit'] = recvLimit
                self._sendOverRealSocket(destSet['realSocket'], SamMessages.streamReceiveLimitMessage(samSocket['samId'], recvLimit)) 
        
        return data
    
    
    def _getNewSamTcpSockets(self, samSocketId, max):
        samSocket = self.samSockets[samSocketId]
        if max==-1 or max >= len(samSocket['newSamInSockets']):
            newConnList = list(samSocket['newSamInSockets'])
            samSocket['newSamInSockets'].clear()
            
            #generate list of (samSockId, remoteDest) tuples
            newConns = []
            for newConn in newConnList:
                newConns.append((newConn, self._getRemoteDestOfSamTcpSocket(newConn)))
                
            #remove from recv set
            if len(newConns) > 0:
                self.recvableSamSockets.remove(samSocketId)
                        
        else:
            newConns = []
            count = 0
            while count < max:
                newConn = samSocket['newSamInSockets'].popleft()
                newConnDest = self._getRemoteDestOfSamTcpSocket(newConn)
                newConns.append((newConn, newConnDest))
                count += 1
        return newConns
    
    
    def _closeSamTcpSocket(self, samSocketId, forceClose):
        samSocket = self.samSockets[samSocketId]        
        
        if samSocket['errorReason'] is None:
            #socket did not fail up to now
            if (not forceClose) and samSocket['outQueueSize'] > 0:
                #still something left to send, wait with closing but set flag
                if not samSocket['waitingForClose']:
                    if samSocket['outQueueSize'] < samSocket['outMaxQueueSize']:
                        self.sendableSamSockets.remove(samSocketId)
                    samSocket['waitingForClose'] = True
            else:
                #nothing left to send, close
                self._removeSamTcpSocket(samSocket, samSocketId)
        else:
            #socket failed already, do final cleanup
            self._removeSamTcpSocket(samSocket, samSocketId)
            
    
    def _failSamTcpSocket(self, samSocketId, errorReason=''):
        samSocket = self.samSockets[samSocketId]
        samId = samSocket['samId']
        destSet = self.samDests[samSocket['destNum']]
        
        if samSocket['waitingForClose']:
            #was actually pending for close
            self._removeSamTcpSocket(samSocket, samSocketId)
        
        else:
            #socket status sets
            if samSocket['connected'] and samSocket['outQueueSize'] < samSocket['outMaxQueueSize']:
                self.sendableSamSockets.remove(samSocketId)
            self.erroredSamSockets.add(samSocketId)
            self.socketActEvent.set()
            
            #set samSocket status
            samSocket['connected'] = False
            samSocket['errorReason'] = errorReason
            samSocket['outMessage'] = None,
            samSocket['outQueue'].clear()
            samSocket['outQueueSize'] = 0
            samSocket['outSendable'] = False
            samSocket['samId'] = None
            
            #remove sam socket from dest info
            if samId > 0:
                del destSet['samOutSockets'][samId]
            else:
                del destSet['samInSockets'][samId]
                

    def _removeSamTcpSocket(self, samSocket, samSocketId):
        #do final cleanup
        samId = samSocket['samId']
        destSet = self.samDests[samSocket['destNum']]
        
        if samSocket['inQueueSize'] > 0:
            #not empty receive buffer
            self.recvableSamSockets.remove(samSocketId)
            
        if samSocket['errorReason'] is None and samSocket['connected'] and (not samSocket['waitingForClose']) and samSocket['outQueueSize'] < samSocket['outMaxQueueSize']:
            #socket did not fail up to now, was not waiting for close and has free space in its send buffer => it was sendable
            self.sendableSamSockets.remove(samSocketId)
            
        if samSocket['errorReason'] is not None:
            #socket failed
            self.erroredSamSockets.remove(samSocketId)
        else:
            #socket was ok
            self._sendOverRealSocket(destSet['realSocket'], SamMessages.streamCloseMessage(samId))
            
        self.allSamSockets.remove(samSocketId)
        
        #remove from dest
        if samId is not None:
            if samId > 0:
                del destSet['samOutSockets'][samId]
            else:
                del destSet['samInSockets'][samId]
            
        del self.samSockets[samSocketId]
        
            
    def _getRemoteDestOfSamTcpSocket(self, samSocketId):
        dest = self.samSockets[samSocketId]['remoteDest']
        return dest
    
    
    def _getUsedInBufferSpaceOfSamTcpSocket(self, samSocketId):
        samSocket = self.samSockets[samSocketId]
        return samSocket['inQueueSize']
    
    
    def _getFreeOutBufferSpaceOfSamTcpSocket(self, samSocketId):
        samSocket = self.samSockets[samSocketId]
        return samSocket['outMaxQueueSize'] - samSocket['outQueueSize']
    
        
    def _getSamSocketType(self, samSocketId):
        samSocket = self.samSockets[samSocketId]
        return samSocket['type']
    
        
    def _getErrorReasonOfSamTcpSocket(self, samSocketId):
        samSocket = self.samSockets[samSocketId]
        return samSocket['errorReason']
    
    
    def _changeInRecvLimitThresholdOfSamTcpSocket(self, samSocketId, inRecvLimitThreshold):
        samSocket = self.samSockets[samSocketId]
        samSocket['inRecvLimitThreshold'] = inRecvLimitThreshold
        
    
    ##SAM UDP SOCKET##
    
    def _sendUDP(self, destSet, data, target):
        realSockNum = destSet['realSocket']
        self._sendOverRealSocket(realSockNum, SamMessages.datagramSendMessage(target, data))
        return len(data)
    
    
    def _recvUDP(self, samSockNum, samSocket, maxMessages, peekOnly):
        if maxMessages <= len(samSocket['inQueue']):
            #just take the entire queue
            messages = list(samSocket['inQueue'])
            if not peekOnly:
                samSocket['inQueue'].clear()
            self.recvableSamSockets.remove(samSockNum)
        else:
            #we only want a part of the queue
            messages = []
            if peekOnly:
                #keep messages in buffer
                count = 0
                while count < maxMessages:
                    messages.append(samSocket['inQueue'][count])
                    count += 1
            else:
                #purge messages out of buffer
                while len(messages) < maxMessages:
                    messages.append(samSocket['inQueue'].popleft())
        return messages
    
    
    ##OTHER INTERNAL##
    
    def _getOwnDestination(self, destNum):
        destSet = self.samDests[destNum]
        return destSet['destKey']
    
    
    def _getSamSocketType(self, samSockNum):
        return self.samSockets[samSockNum]['type']
    

    ##MAIN MESSAGE HANDLER##
    
    def _handleMessage(self, realSockNum, realSockSet, message):
        destSet = self.samDests[realSockSet['destNum']]
        messageType = message['msgType']
        messageParas = message['msgParas']
        if messageType=='HELLO REPLY':
            #handshake reply
            if messageParas['RESULT'].upper()=='OK' and messageParas['VERSION']=='2.0':
                #send session create message
                assert len(realSockSet["outQueue"])==0, "just handshaked and stuff to send?!"
                self._sendOverRealSocket(realSockNum, SamMessages.sessionCreateMessage(destSet['sessionType'], destSet['destName'], destSet['sessionDirection'], destSet['sessionOptions']))
            else:
                #something borked
                self._failDestination(realSockSet['destNum'], "Invalid HELLO REPLY: Result<"+messageParas['RESULT']+"> Version<"+messageParas['VERSION']+">")                
                
        elif messageType=='SESSION STATUS':
            #session established
            if messageParas['RESULT'].upper()=='OK':
                #ok, session is established
                destSet['sessionEstablished'] = True
                self._sendOverRealSocket(realSockNum, "NAMING LOOKUP NAME=ME\n")
                
                if destSet['sessionType']=='udp' or destSet['sessionType']=='raw':
                    #udp-like, has only one socket
                    samSocket = self.samSockets[destSet["samSocket"]]   
                    self.sendableSamSockets.add(destSet["samSocket"])
                    self.socketActEvent.set()
                elif destSet['sessionType']=='tcp':
                    #tcp-like, send STREAM CONNECT message for each outgoing sam socket
                    for samId, samSocketId in destSet['samOutSockets'].iteritems():
                        samSocket = self.samSockets[samSocketId]
                        self._sendOverRealSocket(destSet['realSocket'] ,SamMessages.streamConnectMessage(samId, samSocket['remoteDest']))
            else:
                #urgh
                self._failDestination(realSockSet['destNum'], "Failed to setup session: "+messageParas['RESULT'])
                
        elif messageType=='NAMING REPLY':
            #reply to destination request
            if messageParas['RESULT'].upper()=='OK':
                destSet['destKey'] = messageParas['VALUE']
        
        elif messageType=='DATAGRAM RECEIVED':
            #received datagram
            samSocket = self.samSockets[destSet["samSocket"]]
            if len(samSocket['inQueue']) == 0:
                #first item in queue, add to recvable set
                self.recvableSamSockets.add(destSet["samSocket"])
                self.socketActEvent.set()
                
            samSocket['inQueue'].append((''.join(message['Data']), messageParas['DESTINATION']))
            
        elif messageType=='RAW RECEIVED':
            #received raw data
            samSocket = self.samSockets[destSet["samSocket"]]
            if len(samSocket['inQueue']) == 0:
                #first item in queue, add to recvable set
                self.recvableSamSockets.add(destSet["samSocket"])
                self.socketActEvent.set()
            samSocket['inQueue'].append(''.join(message['Data']))
            
        elif messageType=='STREAM STATUS':
            #a outgoing sam tcp-socket connected ... or failed
            samId = int(messageParas['ID'])
            samSocketId = destSet['samOutSockets'].get(samId, None)
            if samSocketId is not None:
                #sam socket still exists
                samSocket = self.samSockets[samSocketId]
                if messageParas['RESULT']=='OK':
                    #socket connected
                    samSocket['connected'] = True
                    samSocket['outSendable'] = True
                    samSocket['inRecvLimit'] = samSocket['inMaxQueueSize']
                    self.sendableSamSockets.add(samSocketId)
                    self.socketActEvent.set()
                    self._sendOverRealSocket(destSet['realSocket'], SamMessages.streamReceiveLimitMessage(samId, samSocket['inMaxQueueSize']))
                else:
                    #failed
                    self._failSamTcpSocket(samSocketId, errorReason=messageParas['RESULT'])
            
        elif messageType=='STREAM CONNECTED':
            #got a new incomming tcp-like connection
            samId = int(messageParas['ID'])
            self._addIncommingSamTcpSocket(samId, messageParas['DESTINATION'], realSockSet['destNum'])
            
        elif messageType=='STREAM SEND':
            #status info about a previous STREAM SEND command
            #assert messageParas['RESULT']=='OK','buffer was full and we tried to send data?!'
            
            samId = int(messageParas['ID'])
            if samId > 0:
                samSocketId = destSet['samOutSockets'].get(samId, None)
            else:
                samSocketId = destSet['samInSockets'].get(samId, None)
                
            if samSocketId is not None:
                #socket still exists
                samSocket = self.samSockets[samSocketId]
                if messageParas['RESULT']=='OK':
                    #data was send
                    samSocket['outMessage'] = None
                else:
                    #for some reason, the send failed - probably a bug, but a bug in this lib or in sam?
                    if samSocket['errorReason'] is None:
                        #connection did not fail
                        self._pushBackDataFromSamTcpSocket(samSocket, samSocketId, samSocket['outMessage'])
                        samSocket['outMessage'] = None
                        if self.log is not None:
                            self.log.warn("A send for the conn with Id \"%d\" failed, pushing data back into queue", samSocketId)
                if messageParas['STATE']=='READY':
                    #the buffer of the sam bridge is not full, allowed to send more
                    samSocket['outSendable'] = True
                    if samSocket['outQueueSize'] > 0:
                        #send next chunk
                        self._sendDataFromSamTcpSocket(samSocketId)
                    else:
                        if samSocket['waitingForClose']:
                            #was waiting for close and done sending, so close it now
                            self._removeSamTcpSocket(samSocket, samSocketId)
        
        elif messageType=='STREAM READY_TO_SEND':
            samId = int(messageParas['ID'])
            if samId > 0:
                samSocketId = destSet['samOutSockets'].get(samId, None)
            else:
                samSocketId = destSet['samInSockets'].get(samId, None)
                
            if samSocketId is not None:
                #socket still exists
                samSocket = self.samSockets[samSocketId]
                samSocket['outSendable'] = True
                if samSocket['outQueueSize'] > 0:
                    #send next chunk
                    self._sendDataFromSamTcpSocket(samSocketId)
                else:
                    if samSocket['waitingForClose']:
                        #was waiting for close and done sending, so close it now
                        self._removeSamTcpSocket(samSocket, samSocketId)
        
        elif messageType=='STREAM CLOSED':
            samId = int(messageParas['ID'])
            if samId > 0:
                samSocketId = destSet['samOutSockets'].get(samId, None)
            else:
                samSocketId = destSet['samInSockets'].get(samId, None)
                
            if samSocketId is not None:
                if messageParas['RESULT']=='OK':
                    #OK isn't a good error reason ...
                    messageParas['RESULT'] = 'CLOSED_BY_PEER'
                self._failSamTcpSocket(samSocketId, errorReason=messageParas['RESULT'])
        
        elif messageType=='STREAM RECEIVED':
            samId = int(messageParas['ID'])
            if samId > 0:
                samSocketId = destSet['samOutSockets'].get(samId, None)
            else:
                samSocketId = destSet['samInSockets'].get(samId, None)
                
            if samSocketId is not None:
                #sockets still exists
                samSocket = self.samSockets[samSocketId]
                if samSocket['inQueueSize']==0:
                    #inbound buffer was empty until now, add socket to recvable set
                    self.recvableSamSockets.add(samSocketId)
                    self.socketActEvent.set()
                samSocket['inQueue'].append(''.join(message['Data']))
                samSocket['inQueueSize'] += int(messageParas['SIZE'])
                samSocket['inBytesReceived'] += int(messageParas['SIZE'])
                
        else:
            if self.log is not None:
                self.log.warn("Received unknown message from Sam bridge: \"%s\"", message)           
    
    
    ##EXTERNAL - DESTINATION##
    
    def addDestination(self, ip, port, destName, type, direction, sessionOptions={}, defaultInMaxQueueSize=32768, defaultOutMaxQueueSize=32768, defaultInRecvLimitThreshold=None):
        self.lock.acquire()
        if defaultInRecvLimitThreshold is None:
            defaultInRecvLimitThreshold = defaultInMaxQueueSize/2
        result = self._addDestination(ip, port, destName, type, direction, sessionOptions, defaultInMaxQueueSize, defaultOutMaxQueueSize, defaultInRecvLimitThreshold)
        self.lock.release()
        return result
    
    
    def removeDestination(self, destNum):
        self.lock.acquire()
        self._removeDestination(destNum)
        self.lock.release()
        
        
    def changeDefaultQueueSize(self, destNum, defaultInMaxQueueSize=None, defaultOutMaxQueueSize=None):
        self.lock.acquire()
        if destNum in self.samDests:
            destSet = self.samDests[destNum]
            if destSet['sessionType']=='tcp':
                self._changeDefaultQueueSize(destSet, defaultInMaxQueueSize, defaultOutMaxQueueSize)
        self.lock.release()
        
        
    def changeDefaultInRecvLimitThreshold(self, destNum, defaultInRecvLimitThreshold):
        self.lock.acquire()
        if destNum in self.samDests:
            destSet = self.samDests[destNum]
            if destSet['sessionType']=='tcp':
                self._changeDefaultInRecvLimitThreshold(destSet, defaultInRecvLimitThreshold)
        self.lock.release()
        
        
    def changeSamBridgeAddress(self, destNum, ip=None, port=None, reconnect=False):
        self.lock.acquire()
        if destNum in self.samDests:
            self._changeSamBridgeAddress(destNum, ip, port, reconnect)
        self.lock.release()
        
        
    def changeDestinationName(self, destNum, destName, reconnect=False):
        self.lock.acquire()
        if destNum in self.samDests:
            self._changeDestinationName(destNum, destName, reconnect)
        self.lock.release()
        
       
    def changeSessionOption(self, destNum, option, value, reconnect=False):
        self.lock.acquire()
        if destNum in self.samDests:
            self._changeSessionOption(destNum, option, value, reconnect)
        self.lock.release()
        
        
    def removeSessionOption(self, destNum, option, reconnect=False):
        self.lock.acquire()
        if destNum in self.samDests:
            self._removeSessionOption(destNum, option, reconnect)
        self.lock.release()
        
        
    def replaceSessionOptions(self, destNum, sessionOptions, reconnect=False):
        self.lock.acquire()
        if destNum in self.samDests:
            self._replaceSessionOptions(destNum, sessionOptions, reconnect)
        self.lock.release()
        
        
    ##EXTERNAL - SOCKETS##
    
    def connect(self, destNum, targetDest, inMaxQueueSize=32768, outMaxQueueSize=32768, inRecvLimitThreshold=None):
        self.lock.acquire()
        if inRecvLimitThreshold is None:
            inRecvLimitThreshold = inMaxQueueSize/2
        samSocketId = self._addOutgoingSamTcpSocket(targetDest, destNum, inMaxQueueSize, outMaxQueueSize, inRecvLimitThreshold)
        self.lock.release()
        return samSocketId
    
    
    def listen(self, destNum, addOld=False):
        self.lock.acquire()
        destSet = self.samDests[destNum]
        samSocketId = None
        if destSet['sessionType']=='tcp' and destSet['samListenSocket'] is None:
            samSocketId = self._addListeningSamTcpSocket(destNum, addOld)
        self.lock.release()
        return samSocketId
    
    
    def accept(self, samSocketId, max=-1):
        self.lock.acquire()
        newConns = []
        if samSocketId in self.samSockets:
            samSocket = self.samSockets[samSocketId]
            
            if samSocket['type'] == 'tcpListen':
                newConns = self._getNewSamTcpSockets(samSocketId, max)
        self.lock.release()
        return newConns
    
        
    def send(self, samSockNum, data, target=None):
        self.lock.acquire()
        bytesSend = 0
        if samSockNum in self.samSockets:
            #samSockNum is a valid number
            samSocket = self.samSockets[samSockNum]
            destSet = self.samDests[samSocket['destNum']]
            
            
            if destSet['sessionType']=='udp' or destSet['sessionType']=='raw':
                #udp-like transport, the referenced SAM socket is the only socket of that destination, no buffer limits
                if (target is not None) and len(data)<=32768 and destSet['sessionEstablished']==True:
                    #may send
                    bytesSend = self._sendUDP(destSet, data, target)
                    
            elif destSet['sessionType']=='tcp':
                #tcp-like transport
                if samSockNum in self.sendableSamSockets:
                    bytesSend = self._queueDataForSamTcpSocket(destSet, samSocket, samSockNum, data)
            
        self.lock.release()
        return bytesSend
    
    
    def recv(self, samSockNum, max=-1, peekOnly=False):
        self.lock.acquire()
        data = ''
        if samSockNum in self.samSockets:
            #samSockNum is a valid number
            samSocket = self.samSockets[samSockNum]
            destSet = self.samDests[samSocket['destNum']]
            
            if destSet['sessionType']=='udp' or destSet['sessionType']=='raw':
                data = self._recvUDP(samSockNum, samSocket, max, peekOnly)
                
            elif destSet['sessionType']=='tcp':
                if samSockNum in self.recvableSamSockets and samSocket['type'] != 'tcpListen':
                    data = self._recvQueuedDataFromSamTcpSocket(destSet, samSocket, samSockNum, max, peekOnly)
        self.lock.release()
        return data
    
    
    def close(self, samSockNum, forceClose=False):
        self.lock.acquire()
        if samSockNum in self.samSockets:
            #samSockNum is a valid number
            samSocket = self.samSockets[samSockNum]
            
            if samSocket['type']=='udp' or samSocket['type']=='raw':
                #only a single socket, close that one and the dests goes down, too
                self._removeDestination(samSocket['destNum'])
            elif samSocket['type']=='tcpOut' or samSocket['type']=='tcpIn':
                #tcp like
                self._closeSamTcpSocket(samSockNum, forceClose)
            elif samSocket['type']=='tcpListen':
                #tcp listening socket
                self._removeListeningSamTcpSocket(samSocket['destNum'])
                    
        self.lock.release()
        
    
    def getOwnDestination(self, destNum=None, samSockNum=None, timeout=-1):
        self.lock.acquire()
        if destNum is None:
            destNum = self.samSockets[samSockNum]['destNum']
        startTime = time()
        destination = self._getOwnDestination(destNum)
        while destination is None and (timeout==-1 or startTime + timeout >= time()):
            self.lock.release()
            sleep(0.1)
            self.lock.acquire()
            destination = self._getOwnDestination(destNum)
        self.lock.release()
        return destination
    
    
    def getSamSocketRemoteDestination(self, samSocketId):
        self.lock.acquire()
        remoteDest = ''
        if samSocketId in self.samSockets:
            socketType = self.samSockets[samSocketId]['type']
            if socketType=='tcpOut' or socketType=='tcpIn':
                remoteDest = self._getRemoteDestOfSamTcpSocket(samSocketId)
        self.lock.release()
        return remoteDest
    
    
    def getSamSocketUsedInBufferSpace(self, samSocketId):
        self.lock.acquire()
        usedSpace = 0
        if samSocketId in self.samSockets:
            socketType = self.samSockets[samSocketId]['type']
            if socketType=='tcpOut' or socketType=='tcpIn':
                usedSpace = self._getUsedInBufferSpaceOfSamTcpSocket(samSocketId)
        self.lock.release()
        return usedSpace
    
    
    def getSamSocketFreeOutBufferSpace(self, samSocketId):
        self.lock.acquire()
        freeSpace = 0
        if samSocketId in self.samSockets:
            socketType = self.samSockets[samSocketId]['type']
            if socketType=='tcpOut' or socketType=='tcpIn':
                freeSpace = self._getFreeOutBufferSpaceOfSamTcpSocket(samSocketId)
        self.lock.release()
        return freeSpace
    
    
    def getSamSocketType(self, samSocketId):
        self.lock.acquire()
        socketType = 'None'
        if samSocketId in self.samSockets:
            socketType = self._getSamSocketType(samSocketId)
        self.lock.release()
        return socketType
    
    
    def getSamSocketErrorReason(self, samSocketId):
        self.lock.acquire()
        errorReason = 'UNKNOWN_SOCKET'
        if samSocketId in self.samSockets:
            errorReason = self._getErrorReasonOfSamTcpSocket(samSocketId)
        self.lock.release()
        return errorReason
    
    
    def changeInRecvLimitThreshold(self, samSocketId, inRecvLimitThreshold):
        self.lock.acquire()
        if samSocketId in self.samSockets:
            socketType = self.samSockets[samSocketId]['type']
            if socketType=='tcpOut' or socketType=='tcpIn':
                self.changeInRecvLimitThreshold(samSocketId, inRecvLimitThreshold)
        self.lock.release()
        
    
    def select(self, recvInterest, sendInterest, errorInterest, timeout=None):
        self.lock.acquire()   
        startTime = time()
        finished = False
        while finished==False:
            #generate sets
            recvable = recvInterest.intersection(self.recvableSamSockets)
            sendable = sendInterest.intersection(self.sendableSamSockets)
            errored = errorInterest.intersection(self.erroredSamSockets)
            errored.update(errorInterest.difference(self.allSamSockets))
            
            #check if we should stop looping
            if len(recvable)>0 or len(sendable)>0 or len(errored)>0:
                finished = True
            else:
                if timeout is not None:
                    if time()-startTime > timeout:
                        finished = True
                        
            #check if we need to wait
            if finished==False:
                self.lock.release()
                if timeout==None:
                    self.socketActEvent.wait()
                else:
                    self.socketActEvent.wait(timeout + startTime - time())       
                self.socketActEvent.clear()
                self.lock.acquire()                
        
        self.lock.release()
        return recvable, sendable, errored
    
    
    ##EXTERNAL - OTHER
    
    def shutdown(self):
        self.lock.acquire()
        thread = self.thread
        self._removeAllDestinations()
        self.lock.release()
        if thread is not None:
            #wait for thread to die
            thread.join()
        
        self.sockManager.shutdown()
    
    
    ##MAIN LOOP##
    
    def run(self):
        self.lock.acquire()
        try:
            while self.shouldStop==False:
                self.lock.release()
                recvSet, writeSet, errorSet = self.sockManager.select(self.realSocksWithRecvInterest, self.realSocksWithSendInterest, self.allRealSocks, timeout=1)
                self.lock.acquire()
                
                for realSockNum in recvSet:
                    ##read
                    if realSockNum in self.realSocksWithRecvInterest:
                        realSockSet = self.realSockets[realSockNum]
                        data = self.sockManager.recv(realSockNum)
                        messages = []
                        offset = 0
                        #process data
                        while not offset>=len(data):
                            #loop until all received data was processed
                            if realSockSet['inMessage'] is None:
                                #there is no finished message that needs bulk data
                                endOfMessage = data.find('\n', offset)
                                inQueue = realSockSet['inQueue']
                                if endOfMessage==-1:
                                    #only the beginning of a message, store it in the inbound queue
                                    if offset==0:
                                        inQueue.append(data)
                                    else:
                                        inQueue.append(data[offset:])
                                    offset = len(data)
                                else:
                                    #the whole message or the ending
                                    message = data[offset:endOfMessage]
                                    offset = endOfMessage+1
                                    if len(inQueue) > 0:
                                        #get the beginning of the message out of the queue
                                        inQueue.append(message)
                                        message = ''.join(inQueue)
                                        inQueue.clear()
                                    #parse message
                                    if self.log is not None:
                                        self.log.debug("Got Message: \"%s\"", message)
                                    message = SamMessages.parseMessage(message)
                                    #check if we need to wait for more data
                                    if 'SIZE' in message['msgParas']:
                                        message['Data'] = []
                                        message['DataLen'] = 0
                                        realSockSet['inMessage'] = message
                                    else:
                                        messages.append(message)
                            else:
                                #only missing a few bytes here ...
                                inMessage = realSockSet['inMessage']
                                missingBytes = int(inMessage['msgParas']['SIZE']) - inMessage['DataLen']
                                remainingBytes = len(data) - offset
                                if remainingBytes>=missingBytes:
                                    #got all
                                    if remainingBytes==missingBytes and offset==0:
                                        inMessage['Data'].append(data)
                                    else:
                                        inMessage['Data'].append(data[offset:offset+missingBytes])
                                    inMessage['DataLen'] = int(inMessage['msgParas']['SIZE'])
                                    offset += missingBytes
                                    messages.append(inMessage)
                                    realSockSet['inMessage'] = None
                                else:
                                    #still missing a bit
                                    if offset==0:
                                        inMessage['Data'].append(data)
                                    else:
                                        inMessage['Data'].append(data[offset:])
                                    inMessage['DataLen'] += remainingBytes
                                    offset += remainingBytes        
                        #handle messages
                        for msg in messages:
                            self._handleMessage(realSockNum, realSockSet, msg)
                
                for realSockNum in writeSet:
                    ##write
                    if realSockNum in self.realSocksWithSendInterest:
                        realSockSet = self.realSockets[realSockNum]
                        if realSockSet['connected']==False:
                            #connected, send handshake as soon as possible
                            realSockSet['connected'] = True
                            self.realSocksWithRecvInterest.add(realSockNum)
                            self.realSocksWithSendInterest.remove(realSockNum)
                            self._sendOverRealSocket(realSockNum, "HELLO VERSION MIN=2.0 MAX=2.0\n")                        
                        else:
                            #already connected, send data
                            assert len(realSockSet['outQueue']) > 0, 'Empty outbuffer, but trying to send?!'
                            
                            while len(realSockSet['outQueue']) > 0:
                                #still something in the queue, try to send the next message
                                data = realSockSet['outQueue'].popleft()
                                bytesSend = self.sockManager.send(realSockNum, data)
                                if bytesSend < len(data):
                                    #not all data send, push remaining data back into queue and abort loop
                                    realSockSet['outQueue'].appendleft(data[bytesSend:])
                                    break;
                            if len(realSockSet['outQueue']) == 0:
                                #managed to empty the queue, nothing to send anymore
                                self.realSocksWithSendInterest.remove(realSockNum)
                            
                for realSockNum in errorSet:
                    ##error
                    if realSockNum in self.allRealSocks:
                        self._failDestination(self.realSockets[realSockNum]['destNum'], "Connection to SAM failed")
        
            #delete own reference
            self.thread = None
            
        except:
            #main loop crashed
            if self.log is not None:
                #ok, log traceback
                self.log.error("Error in main loop!\nTraceback:\n%s", getTraceback())
        self.lock.release()
        
if __name__ == '__main__':
    print 'startup'
    mang = SamSocketManager()
    
    print 'Creating first UDP socket'
    sockAD, sockA = mang.addDestination('127.0.0.1', 7656, "test", "udp", "both", {'inbound.nickname':"testnick"})
    print 'SockNum:',sockA
    sockADest = mang.getOwnDestination(samSockNum=sockA)
    print 'Dest:',sockADest
    print
    
    print 'Creating second UDP socket'
    sockBD, sockB = mang.addDestination('127.0.0.1', 7656, "test2", "udp", "both", {'inbound.nickname':"testnick2"})
    print 'SockNum:',sockB
    sockBDest = mang.getOwnDestination(samSockNum=sockB)
    print 'Dest:',sockBDest
    
    print 'Sending "TESTMESSAGE" from sockB to sockA'
    mang.send(sockB, "TESTMESSAGE", target=sockADest)
    
    print 'Closing UDP sockets'
    mang.removeDestination(sockAD)
    mang.close(sockB)
    
    print 'Creating first TCP dest'
    resultA = mang.addDestination('127.0.0.1', 7656, "testTcp", "tcp", "both", {'inbound.nickname':"testTcp"})
    resultADest = mang.getOwnDestination(destNum=resultA)
    print 'Creating listener'
    listenSock = mang.listen(resultA)
    print 'Creating second TCP dest'
    resultB = mang.addDestination('127.0.0.1', 7656, "testTcp2", "tcp", "both", {'inbound.nickname':"testTcp2"})
    print 'Connecting to first TCP dest'
    connectSock = mang.connect(resultB, resultADest, outMaxQueueSize=131072)
    print 'Waiting for connection'
    result = mang.select(set(), set((connectSock,)), set((listenSock, connectSock)), 40)
    print 'connected:',result
    result = mang.select(set((listenSock,)), set(), set((listenSock, connectSock)), 40)
    print 'Listener ready:', result
    acceptedSock = mang.accept(listenSock)[0]
    print 'Accepted:',acceptedSock
    print 'Send:',mang.send(connectSock, 100000*'1')
    print 'Recvable:',mang.select(set((acceptedSock,)), set(), set((acceptedSock, listenSock, connectSock)), 10)
    sleep(11)
    data = mang.recv(acceptedSock)
    print 'Recvable:',mang.select(set((acceptedSock,)), set(), set((acceptedSock, listenSock, connectSock)), 10)
    data2 = mang.recv(acceptedSock)
    print 'Received:', data2[:10]
    print 'ReceivedLen:',len(data2)
    
    print 'Closing first TCP dest'
    mang.removeDestination(resultA)
    print 'Closing second TCP dest'
    mang.removeDestination(resultB)
