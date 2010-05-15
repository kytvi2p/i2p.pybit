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

from __future__ import with_statement
from time import sleep
import logging
import socket
import select
import threading

from Utilities import getTraceback




class AsyncSocketManager:
    def __init__(self, log=None):
        self.log = log
        if isinstance(self.log, basestring):
            self.log = logging.getLogger(self.log)
            
        self.sockets = {}            #sockets, key is realSockNum (the socket id)
        
        #sets
        self.allSocks = set()        #ids of all known sockets
        self.workingSocks = set()    #ids of sockets which have not failed
        self.failedSocks = set()     #ids of failed sockets
        
        self.lock = threading.Lock() #the main lock
        
        
    ##internal functions - add, fail and remove
        
    def _addSock(self, sock):
        realSockNum = sock.fileno()
        
        assert realSockNum >= 0, 'Assumption about file descriptors is wrong!'
        assert not (realSockNum in self.allSocks), 'Duplicate socket id?!'
        
        self.sockets[realSockNum] = sock
        self.allSocks.add(realSockNum)
        self.workingSocks.add(realSockNum)
        return realSockNum
    
    
    def _failSock(self, realSockNum):
        self.workingSocks.remove(realSockNum)
        self.failedSocks.add(realSockNum)
    
        
    def _removeSock(self, realSockNum):
        sock = self.sockets[realSockNum]
        sock.close()
        
        del self.sockets[realSockNum]
        self.allSocks.remove(realSockNum)
        self.workingSocks.discard(realSockNum)
        self.failedSocks.discard(realSockNum)

    
    ##internal functions - basic socket functionality
    
    def _accept(self, realSockNum):
        sock = self.sockets[realSockNum]
        newSock = sock.accept()
        if newSock is None:
            result = None
        else:
            newSockNum = self._addSock(newSock[0])
            result = (newSockNum, newSock[1])
        return result
    
    
    def _recv(self, realSockNum, wantedBytes):
        assert wantedBytes > 0, 'want to read 0 bytes?!'
        
        sock = self.sockets[realSockNum]
            
        try:
            data = sock.recv(wantedBytes)
        except socket.error:
            data = ''
        except select.error:
            data = ''
        
        if len(data) == 0:
            self._failSock(realSockNum)
            
        return data
    
    
    def _send(self, realSockNum, data):
        bytesSend = 0
        sock = self.sockets[realSockNum]
        
        try:
            bytesSend = sock.send(data)
        except socket.error:
            self._failSock(realSockNum)
        except select.error:
            self._failSock(realSockNum)
            
        return bytesSend
    
    
    def _close(self, realSockNum):
        self._removeSock(realSockNum)
        
    
    ##external functions - basic socket functionality
    
    def connect(self, addr):
        with self.lock:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setblocking(0)
            sock.connect_ex(addr)
            return self._addSock(sock)
        
    
    def listen(self, addr):
        with self.lock:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setblocking(0)
            sock.bind(addr)
            sock.listen(1)
            return self._addSock(sock)
        
    
    def accept(self, realSockNum):
        with self.lock:
            if not realSockNum in self.workingSocks:
                result = None
            else:
                result = self._accept(realSockNum)
            return result
            
    
    def recv(self, realSockNum, wantedBytes=4096):
        with self.lock:
            if not realSockNum in self.workingSocks:
                data = ''
            else:
                data = self._recv(realSockNum, wantedBytes)
            return data
    
    
    def send(self, realSockNum, data):
        with self.lock:
            if not realSockNum in self.workingSocks:
                bytesSend = 0
            else:
                bytesSend = self._send(realSockNum, data)
            return bytesSend
        
    
    def close(self, realSockNum):
        with self.lock:
            if realSockNum in self.sockets:
                self._close(realSockNum)
                
                
    ##external functions - other
    
    def checkPollEventResults(self, connEvents):
        with self.lock:
            valid = [(realSockNum, eventmask) for realSockNum, eventmask in connEvents if realSockNum in self.workingSocks]
            failedOrInvalid = [(realSockNum, eventmask) for realSockNum, eventmask in connEvents if realSockNum in self.failedSocks or realSockNum not in self.allSocks]
            return valid, failedOrInvalid
        
        
    def shutdown(self):
        with self.lock:
            for realSockNum in self.sockets.keys():
                self._close(realSockNum)
        
            
    ##external functions - select
    
    def select(self, recvInterestSet, sendInterestSet, errorInterestSet, timeout):
        with self.lock:
            recvList = [realSockNum for realSockNum in recvInterestSet if realSockNum in self.workingSocks]
            sendList = [realSockNum for realSockNum in sendInterestSet if realSockNum in self.workingSocks]
            errorList = [realSockNum for realSockNum in errorInterestSet if realSockNum in self.workingSocks]
            
            if len(recvList)==0 and len(sendList)==0 and len(errorList)==0:
                #nothing to do, sleep a moment
                sleep(timeout)
            else:
                #do the select poll
                recvList, sendList, errorList = select.select(recvList, sendList, errorList, timeout)
                
            #build result sets
            recvable = set(recvList)
            sendable = set(sendList)
            errored = set(errorList)
            errored.update(errorInterestSet.intersection(self.failedSocks))
            errored.update(errorInterestSet.difference(self.allSocks))
            
        return recvable, sendable, errored




if __name__ == '__main__':
    print 'startup'
    bla = AsyncSocketManager()
    
    print 'setup listening socket'
    test = socket.socket()
    test.bind(('127.0.0.1',12457))
    test.listen(2)
    test.setblocking(0)
    
    print 'connect'
    sockNum = bla.connect(('127.0.0.1', 12457))
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
