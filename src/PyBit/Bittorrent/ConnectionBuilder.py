"""
Copyright 2009  Blub

ConnectionBuilder, the class which creates connection to other bittorrent clients.
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

from collections import deque
import logging
import threading

from PySamLib.I2PSocket import I2PSocket
import Messages

from Utilities import logTraceback

class ConnectionBuilder:
    def __init__(self, eventScheduler, connHandler, peerPool, destNum, samSockManager, peerId):
        self.sched = eventScheduler
        self.connHandler = connHandler
        self.peerPool = peerPool
        self.destNum = destNum
        self.samSockManager = samSockManager
        self.peerId = peerId
        
        #torrent info
        self.torrents = {}
        
        #connections
        self.allConns = set()  
        self.connsWithSendInterest = set()
        self.connsWithRecvInterest = set()
        self.conns = {}
        
        self.log = logging.getLogger('ConnectionBuilder')
        self.lock = threading.Lock()
        
        #thread
        self.shouldStop = False
        self.thread = threading.Thread(target=self.run)
        self.thread.start()
        
    
    ##torrents
     
    def _addTorrent(self, torrentIdent, infohash):
        peerEvent = self.sched.scheduleEvent(self.getPossiblePeers, timedelta=60, funcArgs=[torrentIdent], repeatdelta=60)
        self.torrents[torrentIdent] = {'conns':set(),
                                       'connAddrs':set(),
                                       'infohash':infohash,
                                       'peerEvent':peerEvent}
                                    
    
    def _removeTorrent(self, torrentIdent):
        torrentInfo = self.torrents[torrentIdent]
        self.sched.removeEvent(torrentInfo['peerEvent'])
        for connId in torrentInfo['conns'].copy():
            self._failedConn(connId, 'torrent stopped')
        del self.torrents[torrentIdent]
        
        
    ##connections
        
    def _getPossiblePeers(self, torrentIdent):
        torrentInfo = self.torrents[torrentIdent]
        wantedConns = 10 - len(self.torrents[torrentIdent]['conns'])
        if wantedConns > 0:
            peerAddrs = self.peerPool.getPossibleConnections(torrentIdent, wantedConns, torrentInfo['connAddrs'])
            for peerAddr in peerAddrs:
                #create conn
                sock = I2PSocket(self.samSockManager, self.destNum)
                sock.setblocking(0)
                sock.connect(peerAddr)
                sockNum = sock.fileno()
                
                self.log.info('%s - conn %i: trying to connect to \"%s\"', torrentIdent, sockNum, peerAddr)
                
                #create timeout event
                timeoutEvent = self.sched.scheduleEvent(self.timeout, timedelta=300, funcArgs=[sockNum])
                
                #update torrent info
                torrentInfo['conns'].add(sockNum)
                torrentInfo['connAddrs'].add(peerAddr)
                
                #update conn info
                self.allConns.add(sockNum)
                self.connsWithSendInterest.add(sockNum)
                self.conns[sockNum] = {'sock':sock,
                                       'torrentIdent':torrentIdent,
                                       'timeout':timeoutEvent,
                                       'inBuffer':deque(),
                                       'inBufferSize':0}
                                
                                
    def _removeConn(self, connId):
        torrentIdent = self.conns[connId]['torrentIdent']
        self.log.info('%s - conn %i: removing', torrentIdent, connId)
        
        #remove from sets
        self.allConns.remove(connId)
        self.connsWithSendInterest.discard(connId)
        self.connsWithRecvInterest.discard(connId)
        
        #remove timeout event
        self.sched.removeEvent(self.conns[connId]['timeout'])
        
        #remove from torrent info
        torrentInfo = self.torrents[torrentIdent]
        torrentInfo['conns'].remove(connId)
        torrentInfo['connAddrs'].remove(self.conns[connId]['sock'].getpeername())
        
        del self.conns[connId]
            
            
    def _failedConn(self, connId, reason):
        torrentIdent = self.conns[connId]['torrentIdent']
        connSet = self.conns[connId]
        conn = connSet['sock']
        self.log.info('%s - conn %i: closing', torrentIdent, connId)
        
        #remove from sets
        self.allConns.remove(connId)
        self.connsWithSendInterest.discard(connId)
        self.connsWithRecvInterest.discard(connId)
        
        #remove timeout event
        self.sched.removeEvent(connSet['timeout'])
        
        #remove from torrent info
        torrentInfo = self.torrents[torrentIdent]
        torrentInfo['conns'].remove(connId)
        torrentInfo['connAddrs'].remove(conn.getpeername())
        
        #close conn
        self.peerPool.failedToConnect(connSet['torrentIdent'], conn.getpeername())
        conn.close(force=True)
        del self.conns[connId]
        

    ##connections - handshake
    
    def _gotFullHandshake(self, connId, connSet):
        data = ''.join(connSet['inBuffer'])
        
        #decode handshake
        length, proto, reserved, infohash, remotePeerId = Messages.decodeHandshake(data)
        
        if not proto.lower() == 'bittorrent protocol':
            #invalid handshake, close conn
            self._failedConn(connId, 'received invalid handshake')
            
        elif not infohash == self.torrents[connSet['torrentIdent']]['infohash']:
            #invalid infohash
            self._failedConn(connId, 'received handshake with wrong infohash')
            
        else:
            #valid handshake
            if not self.peerPool.establishedConnection(connSet['torrentIdent'], connSet['sock'].getpeername()):
                #we already have a connection to this address
                self._failedConn(connId, 'we already have a connection to this address')
                
            else:
                #no connection to this address exists up to now
                self.log.info("Conn %i: Got valid handshake, established connections", connId)
                
                #add to handler
                self.connHandler.addConnection(connSet['torrentIdent'], connSet['sock'], 'out', remotePeerId)
                
                #remove from local structures
                self._removeConn(connId)
    
    
    def _recvFromConn(self, connId):
        connSet = self.conns[connId]
        neededBytes = 68 - connSet['inBufferSize']
        data = connSet['sock'].recv(neededBytes)
        if data != '':
            #got something
            dataLen = len(data)
            connSet['inBuffer'].append(data)
            connSet['inBufferSize'] += dataLen
            
            if connSet['inBufferSize'] == 68:
                #completed handshake
                self._gotFullHandshake(connId, connSet)
                
                
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
                recvable, sendable, errored = self.samSockManager.select(self.connsWithRecvInterest, self.connsWithSendInterest, self.allConns, timeout=1)
                self.lock.acquire()
                
                for connId in errored:
                    #conn failed, close it
                    self._failedConn(connId, 'connection failed')
                    
                for connId in sendable:
                    if connId in self.conns:
                        #connected
                        connSet = self.conns[connId]
                        torrentInfo = self.torrents[connSet['torrentIdent']]
                        connSet['sock'].send(Messages.generateHandshake(torrentInfo['infohash'], self.peerId))
                        self.connsWithSendInterest.remove(connId)
                        self.connsWithRecvInterest.add(connId)
                        
                for connId in recvable:
                    if connId in self.conns:
                        #received data
                        self._recvFromConn(connId)
                        
            self.thread = None
            self.log.info("Stopping")
            self.lock.release()
        except:
            self.log.error('Error in main loop:\n%s', logTraceback())
            
            
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
        
    
    ##external functions - torrents
    
    def addTorrent(self, torrentIdent, infohash):
        self.lock.acquire()
        self._addTorrent(torrentIdent, infohash)
        self.lock.release()
        
        
    def removeTorrent(self, torrentIdent):
        self.lock.acquire()
        self._removeTorrent(torrentIdent)
        self.lock.release()
        
        
    ##external functions - peers
    
    def getPossiblePeers(self, torrentIdent):
        self.lock.acquire()
        if torrentIdent in self.torrents:
            self._getPossiblePeers(torrentIdent)
        self.lock.release()
        
    
    def timeout(self, connId):
        self.lock.acquire()
        if connId in self.allConns:
            self._failedConn(connId, 'timeout')
        self.lock.release()