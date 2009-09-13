"""
Copyright 2009  Blub

ConnectionListener, the class which waits for incomming connections from other
bittorrent clients and exchanges a handshake with them.
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

import logging
import threading

from PySamLib.I2PSocket import I2PSocket
import Messages

from Utilities import logTraceback

class ConnectionListener:
    def __init__(self, eventScheduler, connHandler, peerPool, destNum, samSockManager, peerId):
        self.sched = eventScheduler
        self.connHandler = connHandler
        self.peerPool = peerPool
        self.destNum = destNum
        self.samSockManager = samSockManager
        self.peerId = peerId
        
        #infohash -> torrentIdent mapping
        self.torrents = {}
        
        #connections
        self.allConns = set()       
        self.conns = {}
        
        #listenConn
        self.listenConn = self.samSockManager.listen(self.destNum, addOld=True)
        self.allConns.add(self.listenConn)
        
        self.log = logging.getLogger('ConnectionListener')
        self.lock = threading.Lock()
        
        #thread
        self.shouldStop = False
        self.thread = threading.Thread(target=self.run)
        self.thread.start()
        
    
    ##internal functions - connections
    
    def _acceptConns(self):
        newConns = self.samSockManager.accept(self.listenConn)
        for newConn in newConns:
            self.log.info("Accepted new connection from \"%s\" with Id \"%d\"", newConn[1][:10], newConn[0])
            
            #create timeout event
            timeoutEvent = self.sched.scheduleEvent(self.timeout, timedelta=300, funcArgs=[newConn[0]])
            
            #create socket obj
            sock = I2PSocket(self.samSockManager, self.destNum,  newConn[0], newConn[1], 'tcp')
            sock.setblocking(0)
            
            #add to internal structs
            self.allConns.add(newConn[0])
            self.conns[newConn[0]] = {'sock':sock,
                                      'added':False,
                                      'timeout':timeoutEvent,
                                      'inBuffer':[],
                                      'inBufferSize':0}
            
        
    def _recvFromConn(self, connId):
        connSet = self.conns[connId]
        neededBytes = 68 - connSet['inBufferSize']
        data = connSet['sock'].recv(neededBytes)
        if data != '':
            #got something, add to buffer
            dataLen = len(data)
            connSet['inBuffer'].append(data)
            connSet['inBufferSize'] += dataLen
            bufSize = connSet['inBufferSize']
            
            #check for handshake
            if bufSize >= 48 and bufSize < 68 and bufSize - dataLen < 48:
                #just got enough data to decode short handshake
                self._gotShortHandshake(connId, connSet)
                    
            elif bufSize == 68 and bufSize - dataLen < 48:
                #got the full handshake at once
                success = self._gotShortHandshake(connId, connSet)
                if success:
                    self._gotFullHandshake(connId, connSet)
            
            elif bufSize == 68:
                #completed handshake
                self._gotFullHandshake(connId, connSet)

            
    def _closeConn(self, connId, reason):
        #close the connection
        connSet = self.conns[connId]
        self.log.info("Conn %d: Closing, reason: %s", connId, reason)
        
        #close conn, remove from local structs
        connSet['sock'].close(force=True)
        self.allConns.remove(connId)
        del self.conns[connId]
        
        #remove timeout event
        self.sched.removeEvent(connSet['timeout'])
        
        if connSet['added']:
            #already added to peer pool, need to remove it again
            self.peerPool.lostConnection(connSet['torrentIdent'], connSet['sock'].getpeername())
        
        
        
    ##internal functions - handshake
                                    
    def _gotShortHandshake(self, connId, connSet):
        success = False
        data = ''.join(connSet['inBuffer'])
        connSet['inBuffer'] = [data]
        
        #decode handshake
        length, proto, reserved, infohash = Messages.decodeShortHandshake(data)
        
        if not proto.lower()=='bittorrent protocol':
            #invalid handshake, close conn
            self._closeConn(connId, 'received invalid handshake')
            
        elif not infohash in self.torrents:
            #invalid handshake, close conn
            self._closeConn(connId, 'received handshake with unknown infohash')
            
        else:
            #valid handshake
            connSet['torrentIdent'] = self.torrents[infohash]
            if self.peerPool.establishedConnection(connSet['torrentIdent'], connSet['sock'].getpeername()):
                #no connection to this address exists up to now
                success = True
                connSet['added'] = True
                self.log.info("Conn %d: Got valid handshake, sending response", connId)
                connSet['sock'].send(Messages.generateHandshake(infohash, self.peerId))
                
            else:
                #we already have a connection to this address
                self._closeConn(connId, 'we already have a connection to this address')
        
        return success
    
    
    def _gotFullHandshake(self, connId, connSet):
        self.log.info("Conn %i: Got complete handshake, connection established", connId)
        data = ''.join(connSet['inBuffer'])
        
        #decode handshake
        length, proto, reserved, infohash, remotePeerId = Messages.decodeHandshake(data)
        
        #add to handler
        self.connHandler.addConnection(self.torrents[infohash], connSet['sock'], 'in', remotePeerId)
        
        #remove from local structures
        self.allConns.remove(connId)
        del self.conns[connId]
        
    
    ##internal functions - thread
    
    def _start(self):
        self.shouldStop = False
        if self.thread is None:            
            self.thread = threading.Thread(target=self.run)
            self.thread.start()
            
            
    def _stop(self):
        self.shouldStop = True
        
    
    ##internal functions - main loop
    
    def run(self):
        try:
            self.lock.acquire()
            while not self.shouldStop:
                self.lock.release()
                recvable, sendable, errored = self.samSockManager.select(self.allConns, set(), self.allConns, timeout=1)
                self.lock.acquire()
                
                for connId in errored:
                    if connId in self.allConns:
                        if not connId == self.listenConn:
                            self._closeConn(connId, 'conn failed')
                
                for connId in recvable:
                    if connId in self.allConns:
                        if connId == self.listenConn:
                            #new incomming connections
                            self._acceptConns()
                            
                        else:
                            #received data
                            self.log.debug('Conn %i: Received data', connId)
                            self._recvFromConn(connId)
            
            self.thread = None
            self.log.info("Stopping")
            self.lock.release()
        except:
            self.log.error('Error in main loop:\n%s', logTraceback())
    
    ##external functions - torrents
    
    def addTorrent(self, torrentIdent, infohash):
        self.lock.acquire()
        self.torrents[infohash] = torrentIdent
        self.lock.release()
        
        
    def removeTorrent(self, infohash):
        self.lock.acquire()
        del self.torrents[infohash]
        self.lock.release()
        
    
    ##external functions - connections
    
    def timeout(self, connId):
        self.lock.acquire()
        if connId in self.allConns:
            self._closeConn(connId, 'timeout')
        self.lock.release()
        
        
    ##external functions - thread
    
    def start(self):
        self.lock.acquire()
        self._start()
        self.lock.release()
        
        
    def stop(self):
        self.lock.acquire()
        thread = self.thread
        self._stop()
        self.lock.release()
        if thread is not None:
            thread.join()
        



