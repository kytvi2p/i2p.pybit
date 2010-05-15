"""
Copyright 2009  Blub

I2PSocketManager, a class which handles the communication with SAM-bridges.
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

from time import sleep, time
import logging
import threading

from AsyncPoll import POLLRECV, POLLSEND, POLLERROR
from AsyncSocketManager import AsyncSocketManager
from I2PSocketStatus import I2PSocketStatus
from RealSocketStatus import RealSocketStatus
from Utilities import getTraceback
import SamDestination

class I2PSocketManager:
    def __init__(self, log=None, asmLog=None):
        self.log = log
        if type(self.log) == str:
            self.log = logging.getLogger(self.log)
            
        if type(asmLog) == str:
            asmLog = logging.getLogger(asmLog)
        
        self.realSockManager = AsyncSocketManager(log=asmLog) #handler for real sockets
        self.realSockStatus = RealSocketStatus(self.realSockManager)
        
        self.i2pSockActEvent = threading.Event()
        self.i2pSockStatus = I2PSocketStatus(self.i2pSockActEvent)
        
        self.i2pDests = {} #destination num => destination object
        self.uniqueDestId = 1
                
        self.shouldStop = True
        self.lock = threading.Lock() #the main lock
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
        assert self.i2pSockStatus.getConnAmount() == 0, 'stopping but still i2p conns?!'
        
        self.shouldStop = True
        self.i2pSockActEvent.set()
        if self.log is not None:
            self.log.debug("Stopping thread")     
        
        #for debugging
        assert len(self.i2pDests)==0, 'stopping thread but destinations left?!'
        
        
    ##INTERNAL - destination
    
    def _addDestination(self, ip, port, sessionName, sessionType, sessionDirection, sessionOptions, defaultInMaxQueueSize, defaultOutMaxQueueSize, defaultInRecvLimitThreshold):
        destId = self.uniqueDestId
        self.uniqueDestId += 1
            
        if sessionType=='raw':
            destObj = SamDestination.SamRawDestination(destId, self.realSockManager, self.realSockStatus, self.log,
                                                       ip, port, sessionName, sessionDirection, sessionOptions, self.i2pSockStatus)
            result = (destId, destObj.getI2PSocketId())
        
        elif sessionType=='udp':
            destObj = SamDestination.SamUdpDestination(destId, self.realSockManager, self.realSockStatus, self.log,
                                                       ip, port, sessionName, sessionDirection, sessionOptions, self.i2pSockStatus)
            result = (destId, destObj.getI2PSocketId())
                                                        
        elif sessionType=='tcp':
            destObj = SamDestination.SamTcpDestination(destId, self.realSockManager, self.realSockStatus, self.log,
                                                       ip, port, sessionName, sessionDirection, sessionOptions, self.i2pSockStatus,
                                                       defaultOutMaxQueueSize, defaultInMaxQueueSize, defaultInRecvLimitThreshold)
            result = destId
            
        self.i2pDests[destId] = {'obj':destObj,
                                 'type':sessionType}
                                
        if len(self.i2pDests) == 1:
            #first destination, start threa
            self._start()
        
        return result
    
    
    def _removeDestination(self, destId):
        self.i2pDests[destId]['obj'].shutdown()
        del self.i2pDests[destId]
        
        if len(self.i2pDests) == 0:
            #just removed last destination, stop thread
            self._stop()
        
        
    def _removeAllDestinations(self):
        for destId in self.i2pDests.keys():
            self._removeDestination(destId)
        
        
    ##EXTERNAL - DESTINATION##
    
    def addDestination(self, ip, port, sessionName, sessionType, sessionDirection, sessionOptions={}, defaultInMaxQueueSize=32768, defaultOutMaxQueueSize=32768, defaultInRecvLimitThreshold=None):
        self.lock.acquire()
        if defaultInRecvLimitThreshold is None:
            defaultInRecvLimitThreshold = defaultInMaxQueueSize/2
            
        result = self._addDestination(ip, port, sessionName, sessionType, sessionDirection, sessionOptions, defaultInMaxQueueSize, defaultOutMaxQueueSize, defaultInRecvLimitThreshold)
        self.lock.release()
        return result
    
    
    def removeDestination(self, destId):
        self.lock.acquire()
        self._removeDestination(destId)
        self.lock.release()
        
        
    def changeDefaultQueueSize(self, destId, defaultInMaxQueueSize=None, defaultOutMaxQueueSize=None):
        self.lock.acquire()
        if destId in self.i2pDests:
            destSet = self.i2pDests[destId]
            if destSet['type'] == 'tcp':
                destSet['obj'].changeDefaultQueueSize(defaultInMaxQueueSize, defaultOutMaxQueueSize)
        self.lock.release()
        
        
    def changeDefaultInRecvLimitThreshold(self, destId, defaultInRecvLimitThreshold):
        self.lock.acquire()
        if destId in self.i2pDests:
            destSet = self.i2pDests[destId]
            if destSet['type'] == 'tcp':
                self.changeDefaultInRecvLimitThreshold(defaultInRecvLimitThreshold)
        self.lock.release()
        
        
    def changeSessionAddress(self, destId, ip=None, port=None, reconnect=False):
        self.lock.acquire()
        if destId in self.i2pDests:
            self.i2pDests[destId]['obj'].changeSessionAddress(ip, port, reconnect)
        self.lock.release()
        
        
    def changeSessionName(self, destId, sessionName, reconnect=False):
        self.lock.acquire()
        if destId in self.i2pDests:
            self.i2pDests[destId]['obj'].changeSessionName(sessionName, reconnect)
        self.lock.release()
        
       
    def changeSessionOption(self, destId, option, value, reconnect=False):
        self.lock.acquire()
        if destId in self.i2pDests:
            self.i2pDests[destId]['obj'].changeSessionOption(option, value, reconnect)
        self.lock.release()
        
        
    def removeSessionOption(self, destId, option, reconnect=False):
        self.lock.acquire()
        if destId in self.i2pDests:
            self.i2pDests[destId]['obj'].removeSessionOption(option, reconnect)
        self.lock.release()
        
        
    def replaceSessionOptions(self, destId, sessionOptions, reconnect=False):
        self.lock.acquire()
        if destId in self.i2pDests:
            self.i2pDests[destId]['obj'].replaceSessionOptions(sessionOptions, reconnect)
        self.lock.release()
        
        
    ##EXTERNAL - SOCKETS##
    
    def connect(self, destId, remoteDest, inMaxQueueSize=None, outMaxQueueSize=None, inRecvLimitThreshold=None):
        self.lock.acquire()
        if inRecvLimitThreshold is None and inMaxQueueSize is not None:
            inRecvLimitThreshold = inMaxQueueSize/2
            
        i2pSocketId = self.i2pDests[destId]['obj'].connect(remoteDest, inMaxQueueSize, outMaxQueueSize, inRecvLimitThreshold)
        self.lock.release()
        return i2pSocketId
    
    
    def listen(self, destId, addOld=False):
        self.lock.acquire()
        destSet = self.i2pDests[destId]
        i2pSocketId = None
        if destSet['type']=='tcp':
            i2pSocketId = destSet['obj'].startListening(addOld)
        self.lock.release()
        return i2pSocketId
    
    
    def accept(self, i2pSocketId, max=-1):
        self.lock.acquire()
        newConns = []
        
        if self.i2pSockStatus.getRecvable(i2pSocketId):
            #socket is valid and in the right state
            destId, connType = self.i2pSockStatus.getConnInfo(i2pSocketId)
            
            if connType == 'tcpListen':
                newConns = self.i2pDests[destId]['obj'].accept(max)
                
        self.lock.release()
        return newConns
    
        
    def send(self, i2pSocketId, data, target=None):
        self.lock.acquire()
        bytesSend = 0
        if self.i2pSockStatus.getSendable(i2pSocketId):
            #socket is valid and in the right state
            destId, connType = self.i2pSockStatus.getConnInfo(i2pSocketId)

            if connType == 'udp' or connType == 'raw':
                #udp-like transport, the referenced socket is the only socket of that destination, no buffer limits
                bytesSend = self.i2pDests[destId]['obj'].send(target, data)
                    
            elif connType == 'tcpOut' or connType == 'tcpIn':
                #tcp-like transport
                bytesSend = self.i2pDests[destId]['obj'].send(i2pSocketId, data)
            
        self.lock.release()
        return bytesSend
    
    
    def recv(self, i2pSocketId, max=-1, peekOnly=False):
        self.lock.acquire()
        data = ''
        
        if self.i2pSockStatus.getRecvable(i2pSocketId):
            #socket is valid and in the right state
            destId, connType = self.i2pSockStatus.getConnInfo(i2pSocketId)
            
            if connType == 'udp' or connType == 'raw':
                data = self.i2pDests[destId]['obj'].recv(max, peekOnly)
                
            elif connType == 'tcpOut' or connType == 'tcpIn':
                data = self.i2pDests[destId]['obj'].recv(i2pSocketId, max, peekOnly)
        self.lock.release()
        return data
    
    
    def close(self, i2pSocketId, force=False):
        self.lock.acquire()
        if self.i2pSockStatus.connExists(i2pSocketId):
            #socket is valid
            destId, connType = self.i2pSockStatus.getConnInfo(i2pSocketId)
            
            if connType == 'udp' or connType == 'raw':
                #only a single socket, close that one and the dests goes down, too
                self._removeDestination(destId)
                
            elif connType == 'tcpOut' or connType == 'tcpIn':
                #tcp like
                self.i2pDests[destId]['obj'].close(i2pSocketId, force)
                
            elif connType == 'tcpListen':
                #tcp listening socket
                self.i2pDests[destId]['obj'].stopListening(i2pSocketId)
                    
        self.lock.release()
        
    
    def getOwnDestination(self, destId=None, i2pSocketId=None, timeout=None):
        self.lock.acquire()
        if destId is None:
            destId, connType = self.i2pSockStatus.getConnInfo(i2pSocketId)

        startTime = time()
        destination = self.i2pDests[destId]['obj'].getOwnDestination()
        
        if timeout is not None:
            while destination is None and (timeout == -1 or startTime + timeout >= time()):
                self.lock.release()
                sleep(0.1)
                self.lock.acquire()
                destination = self.i2pDests[destId]['obj'].getOwnDestination()
        self.lock.release()
        return destination
    
    
    def getI2PSocketRemoteDestination(self, i2pSocketId):
        self.lock.acquire()
        remoteDest = ''
        if self.i2pSockStatus.connExists(i2pSocketId):
            #socket is valid
            destId, connType = self.i2pSockStatus.getConnInfo(i2pSocketId)
            
            if connType == 'tcpOut' or connType == 'tcpIn':
                remoteDest = self.i2pDests[destId]['obj'].getI2PSocketRemoteDestination(i2pSocketId)
        self.lock.release()
        return remoteDest
    
    
    def getI2PSocketUsedInBufferSpace(self, i2pSocketId):
        self.lock.acquire()
        usedSpace = 0
        if self.i2pSockStatus.connExists(i2pSocketId):
            #socket is valid
            destId, connType = self.i2pSockStatus.getConnInfo(i2pSocketId)
            
            if connType == 'tcpOut' or connType == 'tcpIn':
                usedSpace = self.i2pDests[destId]['obj'].getI2PSocketUsedInBufferSpace(i2pSocketId)
        self.lock.release()
        return usedSpace
    
    
    def getI2PSocketFreeOutBufferSpace(self, i2pSocketId):
        self.lock.acquire()
        freeSpace = 0
        if self.i2pSockStatus.connExists(i2pSocketId):
            #socket is valid
            destId, connType = self.i2pSockStatus.getConnInfo(i2pSocketId)
            
            if connType == 'tcpOut' or connType == 'tcpIn':
                freeSpace = self.i2pDests[destId]['obj'].getI2PSocketFreeOutBufferSpace(i2pSocketId)
        self.lock.release()
        return freeSpace
    
    
    def getI2PSocketType(self, i2pSocketId):
        self.lock.acquire()
        connType = 'None'
        if self.i2pSockStatus.connExists(i2pSocketId):
            #socket is valid
            destId, connType = self.i2pSockStatus.getConnInfo(i2pSocketId)
        self.lock.release()
        return connType
    
    
    def getI2PSocketErrorReason(self, i2pSocketId):
        self.lock.acquire()
        errorReason = 'UNKNOWN_SOCKET'
        if self.i2pSockStatus.connExists(i2pSocketId):
            #socket is valid
            destId, connType = self.i2pSockStatus.getConnInfo(i2pSocketId)
            
            if connType == 'tcpOut' or connType == 'tcpIn':
                errorReason = self.i2pDests[destId]['obj'].getI2PSocketErrorReason(i2pSocketId)
                
        self.lock.release()
        return errorReason
        
    
    def select(self, recvInterest, sendInterest, errorInterest, timeout=None):
        self.lock.acquire()   
        startTime = time()
        finished = False
        while finished==False:
            #generate sets
            recvable, sendable, errored = self.i2pSockStatus.select(recvInterest, sendInterest, errorInterest)
            
            #check if we should stop looping
            if len(recvable)>0 or len(sendable)>0 or len(errored)>0:
                finished = True
            else:
                if timeout is not None:
                    if time() - startTime > timeout:
                        finished = True
                        
            #check if we need to wait
            if not finished:
                self.lock.release()
                if timeout is None:
                    self.i2pSockActEvent.wait()
                else:
                    self.i2pSockActEvent.wait(timeout + startTime - time())       
                self.i2pSockActEvent.clear()
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
        
        self.realSockManager.shutdown()
    
    
    ##MAIN LOOP##
    
    def run(self):
        self.lock.acquire()
        try:
            while self.shouldStop==False:
                self.lock.release()
                sockEvents = self.realSockStatus.getConnEvents()
                self.lock.acquire()
                
                for realSockId, eventmask in sockEvents:
                    if eventmask & POLLRECV != 0:
                        ##recv
                        if self.realSockStatus.connExists(realSockId):
                            destId = self.realSockStatus.getConnInfo(realSockId)
                            self.i2pDests[destId]['obj'].recvEvent()
                            
                        
                    if eventmask & POLLSEND != 0:
                        ##send
                        if self.realSockStatus.connExists(realSockId):
                            destId = self.realSockStatus.getConnInfo(realSockId)
                            self.i2pDests[destId]['obj'].sendEvent()
                         
                        
                    if eventmask & POLLERROR != 0:
                        ##error
                        if self.realSockStatus.connExists(realSockId):
                            destId = self.realSockStatus.getConnInfo(realSockId)
                            self.i2pDests[destId]['obj'].errorEvent()
        
            #delete own reference
            self.thread = None
            
        except:
            #main loop crashed
            if self.log is not None:
                #ok, log traceback
                self.log.error("Error in main loop!\nTraceback:\n%s", getTraceback())
        self.lock.release()
        
if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(levelname)-8s %(name)-14s %(message)s')
    
    print 'startup'
    mang = I2PSocketManager(log='i2pSocketManager', asmLog='asmSocketManager')
    
    print 'Creating first UDP socket'
    sockAD, sockA = mang.addDestination('127.0.0.1', 7656, "TRANSIENT", "udp", "both", {'inbound.nickname':"testnick"})
    print 'SockNum:',sockA
    sockADest = mang.getOwnDestination(i2pSocketId=sockA, timeout=-1)
    print 'Dest:',sockADest
    print
    
    print 'Creating second UDP socket'
    sockBD, sockB = mang.addDestination('127.0.0.1', 7656, "TRANSIENT", "udp", "both", {'inbound.nickname':"testnick2"})
    print 'SockNum:',sockB
    sockBDest = mang.getOwnDestination(i2pSocketId=sockB, timeout=-1)
    print 'Dest:',sockBDest
    
    print 'Sending "TESTMESSAGE" from sockB to sockA'
    mang.send(sockB, "TESTMESSAGE", target=sockADest)
    
    sleep(10)
    
    print 'Closing UDP sockets'
    mang.removeDestination(sockAD)
    mang.close(sockB)
    
    print 'Creating first TCP dest'
    resultA = mang.addDestination('127.0.0.1', 7656, "TRANSIENT", "tcp", "both", {'inbound.nickname':"testTcp"})
    resultADest = mang.getOwnDestination(destId=resultA, timeout=-1)
    print 'Creating listener'
    listenSock = mang.listen(resultA)
    print 'Creating second TCP dest'
    resultB = mang.addDestination('127.0.0.1', 7656, "TRANSIENT", "tcp", "both", {'inbound.nickname':"testTcp2"})
    print 'Connecting to first TCP dest'
    connectSock = mang.connect(resultB, resultADest, outMaxQueueSize=131072)
    print 'Waiting for connection'
    result = mang.select(set(), set((connectSock,)), set((listenSock, connectSock)), 40)
    print 'connected',connectSock,result
    result = mang.select(set((listenSock,)), set(), set((listenSock, connectSock)), 40)
    print 'Listener',listenSock,'ready:', result
    acceptedSock = mang.accept(listenSock)[0]
    print 'Accepted:',acceptedSock
    acceptedSock = acceptedSock[0]
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
    
    print 'Creating thir TCP dest'
    resultC = mang.addDestination('127.0.0.1', 7656, "TRANSIENT", "tcp", "both", {'inbound.nickname':"dnsTest"})
    resultCDest = mang.getOwnDestination(destId=resultC, timeout=-1)
    
    print 'Connecting to pebcache.i2p'
    connectSock = mang.connect(resultC, 'pebcache.i2p')
    result = mang.select(set(), set((connectSock,)), set((connectSock,)), 40)
    print 'connected',connectSock,result
    print 'closing conn'
    mang.close(connectSock)
    print 'Connecting to announc url of crstrack.i2p'
    connectSock = mang.connect(resultC, 'mm3zx3besctrx6peq5wzzueil237jdgscuvn5ugwilxrwzyuajja.b32.i2p')
    result = mang.select(set(), set((connectSock,)), set((connectSock,)), 40)
    print 'connected',connectSock,result
    print 'Connecting to bogus i2p name'
    connect2Sock = mang.connect(resultC, 'adsgadavcxf4zhgsfduajja.i2p')
    result = mang.select(set(), set((connect2Sock,)), set((connect2Sock,)), 40)
    print 'connected',connect2Sock,result
    print 'Closing third TCP dest'
    mang.removeDestination(resultC)
