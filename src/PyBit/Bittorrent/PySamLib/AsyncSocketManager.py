"""
Copyright 2009  Blub

AsnycSocketManager, a simple class to handle async sockets, simplifying their use.
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
import socket
import select
import threading

from Utilities import getTraceback

  
class SelectingAsyncSocketManager:
    def __init__(self, log=None):
        self.log = log
        if type(self.log)==str:
            self.log = logging.getLogger(self.log)
        
        self.sockets = {}            #key = pseudo socket id, contains dictionary with buffers and state info
        self.realNumToPseudoNum = {} #mapping of pseudo id to real socket number
        self.uniqueSockNum = 1
        self.numberOfSocks = 0
        
        self.recvableSocks = set() #socks with a not empty recv buffer (own buffer)
        self.sendableSocks = set() #socks with a not full send buffer (own buffer)
        self.erroredSocks = set()  #socks which failed        
        self.allSocks = set()      #all socks
        
        self.socksWithErrorCheckInterest = set() #socks which should be checked for errors
        self.socksWithRecvInterest = set()       #socks which may receive data (own buffer not full)
        self.socksWithSendInterest = set()       #socks which have a not empty send buffer (own buffer)
        
        self.socksToClose = set() #socks which should be closed as soon as possible
        
        self.lock = threading.Lock() #the main lock
        self.socketActEvent = threading.Event() #a socket got data, data was send or a socket failed (=real socket activity)
        self.stop = True   #main loop should stop, thread should quit
        self.thread = None #reference to current main-loop thread, if any
        
        
    def _start(self):
        #print 'starting'
        assert self.stop==True, 'not stopped?! out of sync?'
        self.stop = False
        if self.thread is None:
            #old thread already died, start a new one
            self.thread = threading.Thread(target=self.run)
            self.thread.start()
            
            
    def _stop(self):
        #print 'stopping'
        assert self.stop==False, 'stopped?! out of sync?'
        assert self.thread is not None, 'no thread but stopping?!'
        self.stop = True
    
    
    def _add(self, sock, connected, recvBufMaxSize, sendBufMaxSize):
        realSockNum = sock.fileno()
        
        #create mapping
        self.realNumToPseudoNum[realSockNum] = self.uniqueSockNum
        pseudoSockNum = self.uniqueSockNum
        self.uniqueSockNum += 1
        
        #create the necessary data structure
        sockSet = {'socket':sock,\
                   'realSockNum':realSockNum,\
                   'connected':connected,\
                   'error':False,\
                   'recvBufMaxSize':recvBufMaxSize,\
                   'recvBufSize':0,\
                   'recvBuf':[],\
                   'sendBufMaxSize':sendBufMaxSize,\
                   'sendBufSize':0,\
                   'sendBuf':[]}
        self.sockets[pseudoSockNum] = sockSet        
        
        #add it to the right sets
        self.allSocks.add(pseudoSockNum)
        self.socksWithErrorCheckInterest.add(realSockNum)
        if connected:
            self.sendableSocks.add(pseudoSockNum)
            self.socksWithRecvInterest.add(realSockNum)            
        else:
            self.socksWithSendInterest.add(realSockNum)
        
        #start the main thread if necessary
        self.numberOfSocks += 1
        if self.numberOfSocks == 1:
            self._start()
        return pseudoSockNum
    
    
    def _recv(self, pseudoSockNum, maxBytes):
        returnData = ''
        sockSet = self.sockets[pseudoSockNum]
        bytesPossible = sockSet['recvBufSize']
        if bytesPossible > 0:
            #something is in the buffer, return it
            if len(sockSet['recvBuf']) > 1:
                data = ''.join(sockSet['recvBuf'])
            else:
                data = sockSet['recvBuf'][0]
            if maxBytes==-1 or maxBytes>=bytesPossible:
                returnData = data
                sockSet['recvBuf'] = []
                sockSet['recvBufSize'] = 0
                self.recvableSocks.remove(pseudoSockNum)
            else:
                returnData = data[:maxBytes]
                sockSet['recvBuf'] = [data[maxBytes:]]
                sockSet['recvBufSize'] -= maxBytes
                
            if sockSet['connected'] and (not sockSet['error']) and \
               bytesPossible >= sockSet['recvBufMaxSize'] and sockSet['recvBufSize'] < sockSet['recvBufMaxSize']:
                #recv buffer is no longer full
                self.socksWithRecvInterest.add(sockSet['realSockNum'])
        return returnData
    
    
    def _send(self, pseudoSockNum, data):
        bytesSend = 0
        sockSet = self.sockets[pseudoSockNum]
        bytesAllowed = sockSet['sendBufMaxSize'] - sockSet['sendBufSize']
        if sockSet['connected'] and (not sockSet['error']) and bytesAllowed > 0:
            #ok, sending is allowed, add the data to the buffer
            data = data[:bytesAllowed]
            dataLen = len(data)
            sockSet['sendBuf'].append(data)
            sockSet['sendBufSize'] += dataLen
            #check if buffer is full
            if bytesAllowed == dataLen:
                self.sendableSocks.remove(pseudoSockNum)
                
            #check if the buffer was empty before
            if dataLen == sockSet['sendBufSize']:
                self.socksWithSendInterest.add(sockSet['realSockNum'])
            
            bytesSend = dataLen
        return bytesSend
    
    
    def _close(self, pseudoSockNum):
        if self.sockets[pseudoSockNum]['error']:
            #the connection failed before the close
            self.recvableSocks.discard(pseudoSockNum)
            self.erroredSocks.remove(pseudoSockNum)
            self.allSocks.remove(pseudoSockNum)
            del self.sockets[pseudoSockNum]
        else:
            #the connection was alive up to now
            sockSet = self.sockets[pseudoSockNum]
            
            #close socket
            sockSet['socket'].close()
            sockSet['socket'] = None
            
            #remove pseudo id from sets
            self.recvableSocks.discard(pseudoSockNum)
            self.sendableSocks.discard(pseudoSockNum)
            self.erroredSocks.discard(pseudoSockNum)            
            self.allSocks.remove(pseudoSockNum)
            
            #remove real socket id from sets            
            realSockNum = sockSet['realSockNum']
            self.socksWithErrorCheckInterest.remove(realSockNum)
            self.socksWithRecvInterest.discard(realSockNum)
            self.socksWithSendInterest.discard(realSockNum)
            
            #remove from dict
            del self.sockets[pseudoSockNum]
        
            #remove mapping
            del self.realNumToPseudoNum[realSockNum]
        
        #decrement counter, stop thread if necessary
        self.numberOfSocks -= 1
        if self.numberOfSocks == 0:
            self._stop()
        
        
    def _closeAll(self):
        for pseudoSockNum in self.sockets.keys():
            #close each socket
            self._close(pseudoSockNum)
            
        
    def _connError(self, realSockNum):
        #a connection failed, cleanup        
        pseudoSockNum = self.realNumToPseudoNum[realSockNum]
        sockSet = self.sockets[pseudoSockNum]
        
        #change socket state
        sockSet['socket'].close()
        sockSet['socket'] = None
        sockSet['connected'] = False
        sockSet['error'] = True
        
        #remove real socket from sets
        self.socksWithErrorCheckInterest.remove(realSockNum)
        self.socksWithRecvInterest.discard(realSockNum)
        self.socksWithSendInterest.discard(realSockNum)
        
        #pseudo socket set changes
        self.sendableSocks.discard(pseudoSockNum)
        self.erroredSocks.add(pseudoSockNum)
        
        #remove mapping
        del self.realNumToPseudoNum[realSockNum]
        
        
    def add(self, sock, connected=True, recvBufMaxSize=32768, sendBufMaxSize=32768):
        self.lock.acquire()
        sock.setblocking(0)
        pseudoSockNum = self._add(sock, connected, recvBufMaxSize, sendBufMaxSize)         
        self.lock.release()        
        return pseudoSockNum
        
        
    def connect(self, addr, recvBufMaxSize=32768, sendBufMaxSize=32768):
        self.lock.acquire()
        
        #create a non-blocking socket
        sock = socket.socket()
        sock.setblocking(0)
        sock.connect_ex(addr)
        
        pseudoSockNum = self._add(sock, False, recvBufMaxSize, sendBufMaxSize)         
            
        self.lock.release()        
        return pseudoSockNum
    
    
    def close(self, pseudoSockNum):
        self.lock.acquire()
        if pseudoSockNum in self.sockets:
            self.socksToClose.add(pseudoSockNum)
        self.lock.release()
        
        
    def recv(self, pseudoSockNum, maxBytes=-1):
        assert not maxBytes==0, 'So you are trying to receive 0 bytes, hm?'
        self.lock.acquire()
        returnData = ''
        if pseudoSockNum in self.sockets:
            returnData = self._recv(pseudoSockNum, maxBytes)
        
        self.lock.release()
        return returnData
    
    
    def send(self, pseudoSockNum, data):
        self.lock.acquire()
        bytesSend = 0
        if pseudoSockNum in self.sockets:
            bytesSend = self._send(pseudoSockNum, data)
            
        self.lock.release()
        return bytesSend


    def select(self, recvInterest, sendInterest, errorInterest, timeout=None):
        self.lock.acquire()
        
        startTime = time()
        finished = False
        while finished==False:
            #generate sets
            recvable = recvInterest.intersection(self.recvableSocks)
            sendable = sendInterest.intersection(self.sendableSocks)
            errored = errorInterest.intersection(self.erroredSocks)
            errored.update(errorInterest.difference(self.allSocks))
            
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
    
    
    def shutdown(self):
        self.lock.acquire()
        thread = self.thread
        self._closeAll()
        self.lock.release()
        if thread is not None:
            thread.join()
        
        
    def run(self):
        self.lock.acquire()
        try:
            while self.stop==False:
                socketAct = False
                
                #build read, write and error list
                readList = list(self.socksWithRecvInterest)            
                writeList = list(self.socksWithSendInterest)
                errorList = list(self.socksWithErrorCheckInterest)
                self.lock.release()      
                
                if len(readList)==0 and len(writeList)==0 and len(errorList)==0:
                    #nothing to do, sleep a moment
                    sleep(0.1)
                else:
                    #do the select poll
                    readList, writeList, errorList = select.select(readList, writeList, errorList, 1)
                
                self.lock.acquire()
                #process
                for realSockNum in readList: #read
                    pseudoSockNum = self.realNumToPseudoNum[realSockNum]
                    sockSet = self.sockets[pseudoSockNum]
                    #if not sockSet['error']:
                    assert sockSet['connected']==True, 'reading without connection?!'
                    try:
                        allowedBytes = sockSet['recvBufMaxSize'] - sockSet['recvBufSize']
                        if allowedBytes > 0:
                            #still want to read, could have changed if the buffer size changed since the select call (not yet implemented)
                            data = sockSet['socket'].recv(allowedBytes)
                            if data=='':
                                self._connError(realSockNum)
                                socketAct = True
                            else:
                                dataLen = len(data)
                                #print 'Received',dataLen,'bytes'                     
                                #check if first data in buffer
                                if sockSet['recvBuf'] == []:
                                    self.recvableSocks.add(pseudoSockNum)
                                    socketAct = True
                                    
                                #add data to buffer
                                sockSet['recvBuf'].append(data)
                                sockSet['recvBufSize'] += dataLen
                                
                                #check if buffer is full
                                if dataLen == allowedBytes:                                
                                    self.socksWithRecvInterest.remove(realSockNum)
                                
                    except socket.error:
                        self._connError(realSockNum)
                        socketAct = True
                            
                    except select.error:
                        self._connError(realSockNum)
                        socketAct = True
                            
                for realSockNum in errorList: #Errors
                    #print 'ERROR'
                    if realSockNum in self.realNumToPseudoNum:
                        pseudoSockNum = self.realNumToPseudoNum[realSockNum]
                        assert self.sockets[pseudoSockNum]['error']==False,'still mapped but failed?!'
                        self._connError(realSockNum)
                        socketAct = True
                    
                for realSockNum in writeList: #Writes
                    #print 'WRITE'
                    if realSockNum in self.realNumToPseudoNum:
                        pseudoSockNum = self.realNumToPseudoNum[realSockNum]
                        sockSet = self.sockets[pseudoSockNum]
                        assert sockSet['error']==False,'still mapped but failed?!'
                        if not sockSet['connected']:
                            #perhaps connected
                            try:
                                sockSet['socket'].send('')
                                #print 'connected'
                                sockSet['connected'] = True
                                self.sendableSocks.add(pseudoSockNum)
                                self.socksWithRecvInterest.add(realSockNum)
                                self.socksWithSendInterest.remove(realSockNum)
                            except socket.error:
                                self._connError(realSockNum)
                            except select.error:
                                self._connError(realSockNum)
                            socketAct = True
                        else:
                            #writeable
                            try:
                                assert len(sockSet['sendBuf']) > 0,'Want to write but nothing there?!'
                                if len(sockSet['sendBuf']) > 1:
                                    data = ''.join(sockSet['sendBuf'])
                                else:
                                    data = sockSet['sendBuf'][0]
                                dataLen = sockSet['sendBufSize']
                                
                                assert len(data)==dataLen,'Wrong send buffer size?!'
                                bytesSend = sockSet['socket'].send(data)
                                assert bytesSend>0, 'writeable but not a single byte send?!'
                                #print 'Wrote',bytesSend,'bytes'
                                sockSet['sendBufSize'] -= bytesSend
                                
                                if bytesSend < dataLen:
                                    sockSet['sendBuf'] = [data[bytesSend:]] #requeue the not send data
                                else: #all send
                                    sockSet['sendBuf'] = []
                                    self.socksWithSendInterest.remove(realSockNum)
                                if dataLen >= sockSet['sendBufMaxSize'] and sockSet['sendBufSize'] < sockSet['sendBufMaxSize']:
                                    #buffer was full, we send something, so there is space again
                                    self.sendableSocks.add(pseudoSockNum)
                                    socketAct = True
                                    
                            except socket.error:
                                self._connError(realSockNum)
                                socketAct = True
                                
                            except select.error:
                                self._connError(realSockNum)
                                socketAct = True
                            
                for pseudoSockNum in self.socksToClose: #closing
                    self._close(pseudoSockNum)
                self.socksToClose.clear()
                
                if socketAct:
                    self.socketActEvent.set()

            #close old conns
            for pseudoSockNum in self.socksToClose: #closing
                self._close(pseudoSockNum)
            self.socksToClose.clear()
            
            #delete own reference
            self.thread = None    
            
            #just in case, set event
            self.socketActEvent.set()
            
        except:
            #main loop crashed
            if self.log is not None:
                #ok, log traceback
                self.log.error("Error in main loop!\nTraceback:\n%s", getTraceback())

        self.lock.release()
        
        
        
class PollingAsyncSocketManager:
    def __init__(self, log=None):
        self.log = log
        if type(self.log)==str:
            self.log = logging.getLogger(self.log)
        
        self.sockets = {}            #key = pseudo socket id, contains dictionary with buffers and state info
        self.realNumToPseudoNum = {} #mapping of pseudo id to real socket number
        self.uniqueSockNum = 1
        self.numberOfSocks = 0
        
        self.recvableSocks = set() #socks with a not empty recv buffer (own buffer)
        self.sendableSocks = set() #socks with a not full send buffer (own buffer)
        self.erroredSocks = set()  #socks which failed        
        self.allSocks = set()      #all socks
        
        self.socksWithErrorCheckInterest = set() #socks which should be checked for errors
        self.socksWithRecvInterest = set()       #socks which may receive data (own buffer not full)
        self.socksWithSendInterest = set()       #socks which have a not empty send buffer (own buffer)
        
        self.socksToClose = set() #socks which should be closed as soon as possible
        
        self.pollObj = select.poll()
        
        self.lock = threading.Lock() #the main lock
        self.socketActEvent = threading.Event() #a socket got data, data was send or a socket failed (=real socket activity)
        self.stop = True   #main loop should stop, thread should quit
        self.thread = None #reference to current main-loop thread, if any
        
        
    def _start(self):
        #print 'starting'
        assert self.stop==True, 'not stopped?! out of sync?'
        self.stop = False
        if self.thread is None:
            #old thread already died, start a new one
            self.thread = threading.Thread(target=self.run)
            self.thread.start()
        
        
    def _stop(self):
        #print 'stopping'
        assert self.stop==False, 'stopped?! out of sync?'
        assert self.thread is not None, 'no thread but stopping?!'
        self.stop = True
        
        
    def _updatePollRegistering(self, realSockNum):
        events = 0
        if realSockNum in self.socksWithRecvInterest:
            events |= select.POLLIN | select.POLLPRI
            
        if realSockNum in self.socksWithSendInterest:
            events |= select.POLLOUT
        
        if realSockNum in self.socksWithErrorCheckInterest:
            events |= select.POLLERR | select.POLLHUP | select.POLLNVAL
            
        assert events!=0,'Not interested in anything?!'
        self.pollObj.register(realSockNum, events)
        
        
    def _add(self, sock, connected, recvBufMaxSize, sendBufMaxSize):
        realSockNum = sock.fileno()
        
        #create mapping
        self.realNumToPseudoNum[realSockNum] = self.uniqueSockNum
        pseudoSockNum = self.uniqueSockNum
        self.uniqueSockNum += 1
        
        #create the necessary data structure
        sockSet = {'socket':sock,\
                   'realSockNum':realSockNum,\
                   'connected':connected,\
                   'error':False,\
                   'recvBufMaxSize':recvBufMaxSize,\
                   'recvBufSize':0,\
                   'recvBuf':[],\
                   'sendBufMaxSize':sendBufMaxSize,\
                   'sendBufSize':0,\
                   'sendBuf':[]}
        self.sockets[pseudoSockNum] = sockSet        
        
        #add it to the right sets
        self.allSocks.add(pseudoSockNum)
        self.socksWithErrorCheckInterest.add(realSockNum)
        if connected:
            self.sendableSocks.add(pseudoSockNum)
            self.socksWithRecvInterest.add(realSockNum)            
        else:
            self.socksWithSendInterest.add(realSockNum)
       
        #add to polling object
        self._updatePollRegistering(realSockNum)
        
        #start the main thread if necessary
        self.numberOfSocks += 1
        if self.numberOfSocks == 1:
            self._start()
        return pseudoSockNum
    
    
    def _recv(self, pseudoSockNum, maxBytes):
        returnData = ''
        sockSet = self.sockets[pseudoSockNum]
        bytesPossible = sockSet['recvBufSize']
        if bytesPossible > 0:
            #something is in the buffer, return it
            if len(sockSet['recvBuf']) > 1:
                data = ''.join(sockSet['recvBuf'])
            else:
                data = sockSet['recvBuf'][0]
            if maxBytes==-1 or maxBytes>=bytesPossible:
                returnData = data
                sockSet['recvBuf'] = []
                sockSet['recvBufSize'] = 0
                self.recvableSocks.remove(pseudoSockNum)
            else:
                returnData = data[:maxBytes]
                sockSet['recvBuf'] = [data[maxBytes:]]
                sockSet['recvBufSize'] -= maxBytes
                
            if sockSet['connected'] and (not sockSet['error']) and \
               bytesPossible >= sockSet['recvBufMaxSize'] and sockSet['recvBufSize'] < sockSet['recvBufMaxSize']:
                #recv buffer is no longer full
                self.socksWithRecvInterest.add(sockSet['realSockNum'])
                self._updatePollRegistering(sockSet['realSockNum'])
        return returnData
    
    
    def _send(self, pseudoSockNum, data):
        bytesSend = 0
        sockSet = self.sockets[pseudoSockNum]
        bytesAllowed = sockSet['sendBufMaxSize'] - sockSet['sendBufSize']
        if sockSet['connected'] and (not sockSet['error']) and bytesAllowed > 0:
            #ok, sending is allowed, add the data to the buffer
            data = data[:bytesAllowed]
            dataLen = len(data)
            sockSet['sendBuf'].append(data)
            sockSet['sendBufSize'] += dataLen
            #check if buffer is full
            if bytesAllowed == dataLen:
                self.sendableSocks.remove(pseudoSockNum)
                
            #check if the buffer was empty before
            if dataLen == sockSet['sendBufSize']:
                self.socksWithSendInterest.add(sockSet['realSockNum'])
                self._updatePollRegistering(sockSet['realSockNum'])
            
            bytesSend = dataLen
        return bytesSend
    
    
    def _close(self, pseudoSockNum):
        if self.sockets[pseudoSockNum]['error']:
            #the connection failed before the close
            self.recvableSocks.discard(pseudoSockNum)
            self.erroredSocks.remove(pseudoSockNum)
            self.allSocks.remove(pseudoSockNum)
            del self.sockets[pseudoSockNum]
        else:
            #the connection was alive up to now
            sockSet = self.sockets[pseudoSockNum]
            
            #close socket
            sockSet['socket'].close()
            sockSet['socket'] = None
            
            #remove pseudo id from sets
            self.recvableSocks.discard(pseudoSockNum)
            self.sendableSocks.discard(pseudoSockNum)
            self.erroredSocks.discard(pseudoSockNum)            
            self.allSocks.remove(pseudoSockNum)
            
            #remove real socket id from sets            
            realSockNum = sockSet['realSockNum']
            self.socksWithErrorCheckInterest.remove(realSockNum)
            self.socksWithRecvInterest.discard(realSockNum)
            self.socksWithSendInterest.discard(realSockNum)
            
            #unregister from polling object
            self.pollObj.unregister(realSockNum)
            
            #remove from dict
            del self.sockets[pseudoSockNum]
        
            #remove mapping
            del self.realNumToPseudoNum[realSockNum]
        
        #decrement counter, stop thread if necessary
        self.numberOfSocks -= 1
        if self.numberOfSocks == 0:
            self._stop()
            
        
    def _closeAll(self):
        for pseudoSockNum in self.sockets.keys():
            #close each socket
            self.socksToClose.add(pseudoSockNum)
        
        
    def _connError(self, realSockNum):
        #a connection failed, cleanup        
        pseudoSockNum = self.realNumToPseudoNum[realSockNum]
        sockSet = self.sockets[pseudoSockNum]
        
        #change socket state
        sockSet['socket'].close()
        sockSet['socket'] = None
        sockSet['connected'] = False
        sockSet['error'] = True
        
        #remove real socket from sets
        self.socksWithErrorCheckInterest.remove(realSockNum)
        self.socksWithRecvInterest.discard(realSockNum)
        self.socksWithSendInterest.discard(realSockNum)
        
        #unregister real socket from polling object
        self.pollObj.unregister(realSockNum)
        
        #pseudo socket set changes
        self.sendableSocks.discard(pseudoSockNum)
        self.erroredSocks.add(pseudoSockNum)
        
        #remove mapping
        del self.realNumToPseudoNum[realSockNum]
        
        
    def add(self, sock, connected=True, recvBufMaxSize=32768, sendBufMaxSize=32768):
        self.lock.acquire()
        sock.setblocking(0)
        pseudoSockNum = self._add(sock, connected, recvBufMaxSize, sendBufMaxSize)         
        self.lock.release()        
        return pseudoSockNum
        
        
    def connect(self, addr, recvBufMaxSize=32768, sendBufMaxSize=32768):
        self.lock.acquire()
        
        #create a non-blocking socket
        sock = socket.socket()
        sock.setblocking(0)
        sock.connect_ex(addr)
        
        pseudoSockNum = self._add(sock, False, recvBufMaxSize, sendBufMaxSize)         
            
        self.lock.release()        
        return pseudoSockNum
    
    
    def close(self, pseudoSockNum):
        self.lock.acquire()
        if pseudoSockNum in self.sockets:
            self.socksToClose.add(pseudoSockNum)
        self.lock.release()
        
        
    def recv(self, pseudoSockNum, maxBytes=-1):
        assert not maxBytes==0, 'So you are trying to receive 0 bytes, hm?'
        self.lock.acquire()
        returnData = ''
        if pseudoSockNum in self.sockets:
            returnData = self._recv(pseudoSockNum, maxBytes)
        
        self.lock.release()
        return returnData
        
        
    def send(self, pseudoSockNum, data):
        self.lock.acquire()
        bytesSend = 0
        if pseudoSockNum in self.sockets:
            bytesSend = self._send(pseudoSockNum, data)
            
        self.lock.release()
        return bytesSend


    def select(self, recvInterest, sendInterest, errorInterest, timeout=None):
        self.lock.acquire()
        
        startTime = time()
        finished = False
        while finished==False:
            #generate sets
            recvable = recvInterest.intersection(self.recvableSocks)
            sendable = sendInterest.intersection(self.sendableSocks)
            errored = errorInterest.intersection(self.erroredSocks)
            errored.update(errorInterest.difference(self.allSocks))
            
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
        
    
    def shutdown(self):
        self.lock.acquire()
        thread = self.thread
        self._closeAll()
        self.lock.release()
        if thread is not None:
            thread.join()
    
    
    def run(self):
        self.lock.acquire()
        try:
            while self.stop==False:
                socketAct = False
                self.lock.release()
                
                #get events
                events = self.pollObj.poll(1000)

                self.lock.acquire()
                #process
                for realSockNum, event in events:
                        
                    if (event & select.POLLIN) != 0: #read
                        #print 'READ'
                        pseudoSockNum = self.realNumToPseudoNum[realSockNum]
                        sockSet = self.sockets[pseudoSockNum]
                        #if not sockSet['error']:
                        assert sockSet['connected']==True, 'reading without connection?!'
                        try:
                            allowedBytes = sockSet['recvBufMaxSize'] - sockSet['recvBufSize']
                            if allowedBytes > 0:
                                #still want to read, could have changed if the buffer size changed since the select call (not yet implemented)
                                data = sockSet['socket'].recv(allowedBytes)
                                if data=='':
                                    self._connError(realSockNum)
                                    socketAct = True
                                else:
                                    dataLen = len(data)
                                    #print 'Received',dataLen,'bytes'                     
                                    #check if first data in buffer
                                    if sockSet['recvBuf'] == []:
                                        self.recvableSocks.add(pseudoSockNum)
                                        socketAct = True
                                        
                                    #add data to buffer
                                    sockSet['recvBuf'].append(data)
                                    sockSet['recvBufSize'] += dataLen
                                    
                                    #check if buffer is full
                                    if dataLen == allowedBytes:                                
                                        self.socksWithRecvInterest.remove(realSockNum)
                                        self._updatePollRegistering(realSockNum)
                                    
                        except socket.error:
                            self._connError(realSockNum)
                            socketAct = True
                                
                        except select.error:
                            self._connError(realSockNum)
                            socketAct = True
                                
                    if (event & select.POLLERR) != 0 or (event & select.POLLHUP) != 0 or (event & select.POLLNVAL) != 0: #Errors
                        #print 'ERROR'
                        if realSockNum in self.realNumToPseudoNum:
                            pseudoSockNum = self.realNumToPseudoNum[realSockNum]
                            assert self.sockets[pseudoSockNum]['error']==False,'still mapped but failed?!'
                            self._connError(realSockNum)
                            socketAct = True
                        
                    if (event & select.POLLOUT) != 0: #Writes
                        #print 'WRITE'
                        if realSockNum in self.realNumToPseudoNum:
                            pseudoSockNum = self.realNumToPseudoNum[realSockNum]
                            sockSet = self.sockets[pseudoSockNum]
                            assert sockSet['error']==False,'still mapped but failed?!'
                            if not sockSet['connected']:
                                #perhaps connected
                                try:
                                    sockSet['socket'].send('')
                                    #print 'connected'
                                    sockSet['connected'] = True
                                    self.sendableSocks.add(pseudoSockNum)
                                    self.socksWithRecvInterest.add(realSockNum)
                                    self.socksWithSendInterest.remove(realSockNum)
                                    self._updatePollRegistering(realSockNum)
                                except socket.error:
                                    self._connError(realSockNum)
                                except select.error:
                                    self._connError(realSockNum)
                                socketAct = True
                            else:
                                #writeable
                                try:
                                    assert len(sockSet['sendBuf']) > 0,'Want to write but nothing there?!'
                                    if len(sockSet['sendBuf']) > 1:
                                        data = ''.join(sockSet['sendBuf'])
                                    else:
                                        data = sockSet['sendBuf'][0]
                                    dataLen = sockSet['sendBufSize']
                                    
                                    assert len(data)==dataLen,'Wrong send buffer size?!'
                                    bytesSend = sockSet['socket'].send(data)
                                    assert bytesSend>0, 'writeable but not a single byte send?!'
                                    #print 'Wrote',bytesSend,'bytes'
                                    sockSet['sendBufSize'] -= bytesSend
                                    
                                    if bytesSend < dataLen:
                                        sockSet['sendBuf'] = [data[bytesSend:]] #requeue the not send data
                                    else: #all send
                                        sockSet['sendBuf'] = []
                                        self.socksWithSendInterest.remove(realSockNum)
                                        self._updatePollRegistering(realSockNum)
                                    if dataLen >= sockSet['sendBufMaxSize'] and sockSet['sendBufSize'] < sockSet['sendBufMaxSize']:
                                        #buffer was full, we send something, so there is space again
                                        self.sendableSocks.add(pseudoSockNum)
                                        socketAct = True
                                        
                                except socket.error:
                                    self._connError(realSockNum)
                                    socketAct = True
                                    
                                except select.error:
                                    self._connError(realSockNum)
                                    socketAct = True
                                
                for pseudoSockNum in self.socksToClose: #closing
                    self._close(pseudoSockNum)
                self.socksToClose.clear()
                
                if socketAct:
                    self.socketActEvent.set()

            #close old conns
            for pseudoSockNum in self.socksToClose: #closing
                self._close(pseudoSockNum)
            self.socksToClose.clear()
            
            #delete own reference
            self.thread = None    
            
            #just in case, set event
            self.socketActEvent.set()
            
        except:
            #main loop crashed
            if self.log is not None:
                #ok, log traceback
                self.log.error("Error in main loop!\nTraceback:\n%s", getTraceback())

        self.lock.release()
        
        
try:
    testObj = select.poll()
    del testObj
    AsyncSocketManager = PollingAsyncSocketManager
except:
    AsyncSocketManager = SelectingAsyncSocketManager


if __name__ == '__main__':
    print 'startup'
    bla = AsyncSocketManager()
    
    print 'setup listening socket'
    test = socket.socket()
    test.bind(('127.0.0.1',12457))
    test.listen(2)
    test.setblocking(0)
    
    print 'connect'
    sockNum = bla.connect(('127.0.0.1', 12457), 1000000)
    print sockNum
    
    print 'select'
    print bla.select(set([sockNum]), set([sockNum]), set([sockNum]))
    
    print 'accept'
    sock = test.accept()[0]
    #sock.setblocking(0)
    
    print 'send'
    print sock.send(1000000*'1')
    
    print 'select'
    print bla.select(set([sockNum]), set([]), set([sockNum]), timeout=1)
    
    print 'receive'
    print len(bla.recv(sockNum))
    
    print 'close listening'
    test.close()
    sock.close()
    
    print 'send'
    print bla.send(sockNum, 10*'1')
    
    print bla.select(set([]), set([]), set([sockNum]), timeout=1)
    
    print 'close socket'
    bla.close(sockNum)
    
