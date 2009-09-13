"""
Copyright 2009  Blub

ConnectionHandler, the class which handles all active connection and messages which are
received from other bittorrent clients.
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

from Connection import Connection
from ConnectionStatus import ConnectionStatus
import Messages

from Utilities import logTraceback

class ConnectionHandler:
    def __init__(self, config, peerPool, selectFunc, scheduler, inLimiter, outLimiter, peerId):
        self.config = config
        self.peerPool = peerPool
        self.selectFunc = selectFunc
        self.scheduler = scheduler
        
        self.inLimiter = inLimiter
        self.outLimiter = outLimiter
        self.ownPeerId = peerId
        
        self.connStatus = ConnectionStatus()
        
        self.conns = {}
        self.torrents = {}
        
        self.log = logging.getLogger('ConnectionHandler')
        
        self.lock = threading.Lock()        
        self.shouldStop = False
        self.thread = None
        self._start()
        
   
    ##internal functions - connections
    
    def _addConnection(self, torrentIdent, connSock, direction, remotePeerId):
        assert torrentIdent in self.torrents,'connection for not running torrent or something?!'
        torrent = self.torrents[torrentIdent]
        remoteAddr = connSock.getpeername()
        assert not remoteAddr in torrent['connRemoteAddrs'],'Already have a connection to that address?!'
        
        if remotePeerId in torrent['connPeerIds']:
            #already connected to this peer
            self.log.info('Closing conn to "%s" because we are already connected to that peer', remoteAddr[:10])
            connSock.close()
            self.peerPool.lostConnection(torrentIdent, remoteAddr)
        else:
            #really add this conn
            conn = Connection(torrentIdent, self.connStatus, torrent['globalStatus'], self.scheduler,\
                              connSock, direction, remotePeerId, remoteAddr,\
                              torrent['inMeasure'], torrent['outMeasure'], self.outLimiter, self.inLimiter)
            connId = conn.fileno()
            self.conns[connId] = conn
            torrent['connIds'].add(connId)
            torrent['connPeerIds'].add(remotePeerId)
            torrent['connRemoteAddrs'].add(remoteAddr)
            
            #send bitfield
            conn.send(Messages.generateBitfield(torrent['ownStatus'].getBitfield()))
            
            
    def _getAllConnections(self, torrentIdent):
        conns = deque()
        for connId in self.torrents[torrentIdent]['connIds']:
            conns.append(self.conns[connId])
        return conns
            
    
    def _removeConnection(self, connId, reason, keepInPool=True):
        conn = self.conns[connId]
        del self.conns[connId]
        
        self.log.info('Closing connection to "%s", reason: %s', conn.getShortRemotePeerAddr(), reason)
        
        remoteAddr = conn.getRemotePeerAddr()
        torrentIdent = conn.getTorrentIdent()
        torrent = self.torrents[torrentIdent]
        torrent['connIds'].remove(connId)
        torrent['connPeerIds'].remove(conn.getRemotePeerId())
        torrent['connRemoteAddrs'].remove(remoteAddr)
        torrent['requester'].connGotClosed(conn)
        conn.close()
        
        self.peerPool.lostConnection(torrentIdent, remoteAddr, keepInPool)
    
    def _removeAllConnectionsOfTorrent(self, torrentIdent):
        for connId in self.torrents[torrentIdent]['connIds'].copy():
            self._removeConnection(connId, "removing torrent")
        
    
    ##internal functions - torrents
    
    def _addTorrent(self, torrentIdent, torrent, globalStatus, inMeasure, outMeasure, storage, requester):
        assert torrentIdent not in self.torrents
        self.torrents[torrentIdent] = {'torrent':torrent,
                                       'globalStatus':globalStatus,
                                       'inMeasure':inMeasure,
                                       'outMeasure':outMeasure,
                                       'storage':storage,
                                       'ownStatus':storage.getStatus(),
                                       'requester':requester,
                                       'connIds':set(),
                                       'connPeerIds':set(),
                                       'connRemoteAddrs':set()}
                                    
                                    
    def _getTorrentInfo(self, conn):
        return self.torrents[conn.getTorrentIdent()]
                                
                                
    def _removeTorrent(self, torrentIdent):
        self._removeAllConnectionsOfTorrent(torrentIdent)
        del self.torrents[torrentIdent]

    
    ##internal functions - messages
    
    def _checkMessage(self, conn, msgNum, message):
        shouldProcess = False
        if message[0]==None:
            #corrupt message
            self.log.debug('Got corrupted message from "%s"', conn.getShortRemotePeerAddr())
            
        elif message[0]==-1:
            #keepalive
            shouldProcess = True
            
        elif message[0]==0:
            #remote choke
            if conn.remoteChoked():
                self.log.info('Got choked from "%s" and we were already choked!', conn.getShortRemotePeerAddr())
            else:
                shouldProcess = True
            
        elif message[0]==1:
            #remote unchoke
            if not conn.localInterested():
                self.log.info('Got unchoked from "%s" and we were not interested. Allowing it because its common practice - doesn\'t mean that it isn\'t stupid.', conn.getShortRemotePeerAddr())
                shouldProcess = True
            if not conn.remoteChoked():
                self.log.info('Got unchoked from "%s" and we were already unchoked!', conn.getShortRemotePeerAddr())
            else:
                shouldProcess = True
                
        elif message[0]==2:
            #remote interested
            if conn.remoteInterested():
                self.log.info('Got interested from "%s" and they already told us before!', conn.getShortRemotePeerAddr())
            elif not self._getTorrentInfo(conn)['ownStatus'].hasMatchingGotPieces(conn.getStatus().getMissingPieces()):
                self.log.info('Got interested from "%s" and we have nothing to send them. What do they want?! - still processing because peers are dumb', conn.getShortRemotePeerAddr())
                shouldProcess = True
            else:
                shouldProcess = True
                
        elif message[0]==3:
            #remote not interested
            if not conn.remoteInterested():
                self.log.info('Got not interested from "%s" and they already told us before!', conn.getShortRemotePeerAddr())
            elif conn.getAmountOfOutRequests() > 0:
                self.log.info('Got not interested from "%s" while a running request existed! Choking them and aborting all running requests!', conn.getShortRemotePeerAddr())
                shouldProcess = True
            else:
                shouldProcess = True
                
        elif message[0]==4:
            #remote got a new piece
            if not self._getTorrentInfo(conn)['torrent'].isValidPiece(message[1]):
                self.log.info('"%s" finished piece "%d" which is not a valid piece ...',
                              conn.getShortRemotePeerAddr(), message[1])
            elif conn.getStatus().hasPiece(message[1]):
                self.log.info('"%s" finished piece "%d" which it already had ...',
                              conn.getShortRemotePeerAddr(), message[1])
            else:
                shouldProcess = True
                
        elif message[0]==5:
            #remotes bitfield
            normalLength = self._getTorrentInfo(conn)['torrent'].getTotalAmountOfPieces()
            if not normalLength%8==0:
                normalLength += (8 - normalLength%8)
                
            if not normalLength==len(message[1]):
                self.log.info('bitfield from "%s" has the wrong size! (Wanted: %d Got: %d)',
                              conn.getShortRemotePeerAddr(), normalLength, len(message[1]))
                            
            elif msgNum > 1:
                self.log.info('bitfield from "%s" was received as the %dth message!',
                              conn.getShortRemotePeerAddr(), msgNum)

            else:
                shouldProcess = True
                
        elif message[0]==6:
            #remote request
            if not self._getTorrentInfo(conn)['torrent'].isValidRequest(message[1][0], message[1][1], message[1][2]):
                self.log.info('Got request from "%s" for piece "%d" with offset "%d" and length "%d" - which is insane ...',
                              conn.getShortRemotePeerAddr(), message[1][0], message[1][1], message[1][2])
                            
            elif conn.getStatus().hasPiece(message[1][0]):
                self.log.info('"%s" requests piece "%d" which it already has ...',
                               conn.getShortRemotePeerAddr(), message[1][0])
                            
            elif conn.getAmountOfOutRequests()==32:
                self.log.info('"%s" requests parts of piece "%d" while having already 32 requests queued - that greedy bastard!',
                               conn.getShortRemotePeerAddr(), message[1][0])
                            
            elif message[1][2]>131072:
                self.log.info('"%s" requests piece "%d" with offset "%d" and length "%d" - look at the freakin length!',
                              conn.getShortRemotePeerAddr(), message[1][0], message[1][1], message[1][2])
                            
            elif conn.localChoked():
                self.log.info('Got request from "%s" for piece "%d" with offset "%d" and length "%d" but it is chocked - probably just normal sync issues',
                              conn.getShortRemotePeerAddr(), message[1][0], message[1][1], message[1][2])
                            
            else:
                shouldProcess = True
            
        elif message[0]==7:
            #got data
            if not conn.hasThisInRequest(message[1][0], message[1][1], len(message[1][2])):
                self.log.info('Got data from "%s": for piece "%d" with offset "%d" and length "%d" but thats not what we requested - probably just normal sync issues',
                              conn.getShortRemotePeerAddr(), message[1][0], message[1][1], len(message[1][2]))
                            
            else:
                shouldProcess = True

        elif message[0]==8:
            #cancel
            if not conn.hasThisOutRequest(message[1][0],message[1][1],message[1][2]):
                self.log.info('Got cancel request from "%s" for piece "%d" with offset "%d" and length "%d" but we do not have any such request queued for them - probably just normal sync issues',
                              conn.getShortRemotePeerAddr(), message[1][0], message[1][1], message[1][2])
                
            else:
                shouldProcess = True
        else:
            self.log.info('Got unknown message with type "%d" from "%s" - ignoring it',
                          message[0], conn.getShortRemotePeerAddr())
                        
        return shouldProcess
    

    def _handleMessage(self, connId, conn, message):
        if message[0]==-1:
            #keepalive
            self.log.debug('Got keepalive from "%s"', conn.getShortRemotePeerAddr())
            
        elif message[0]==0:
            #remote choke
            self.log.debug('Got choked from "%s"', conn.getShortRemotePeerAddr())
            self._getTorrentInfo(conn)['requester'].connGotChoked(conn)
            conn.setRemoteChoke(True)
            
        elif message[0]==1:
            #remote unchoke
            self.log.debug('Got unchoked from "%s"', conn.getShortRemotePeerAddr())
            conn.setRemoteChoke(False)
            if conn.localInterested():
                #and we are interested - means there should be something requestable
                self._getTorrentInfo(conn)['requester'].connGotUnchoked(conn)  
            
        elif message[0]==2:
            #remote interested
            self.log.debug('"%s" is interested in us', conn.getShortRemotePeerAddr())
            conn.setRemoteInterest(True)
            
        elif message[0]==3:
            #remote not interested
            self.log.debug('"%s" is no longer interested in us', conn.getShortRemotePeerAddr())
            conn.setRemoteInterest(False)
                
        elif message[0]==4:
            #remote got a new piece
            self.log.debug('"%s" finished piece "%d"',\
                           conn.getShortRemotePeerAddr(), message[1])
            torrent = self._getTorrentInfo(conn)
            status = conn.getStatus()
            status.gotPiece(message[1])
            
            if torrent['ownStatus'].isSeed() and status.isSeed():
                #both seeds, disconnect
                self._removeConnection(connId, "is seed and we are also a seed", False)
            
            else:
                if (not conn.localInterested()) and (not torrent['ownStatus'].hasPiece(message[1])):
                    #we were not interested, but now this peer got a piece we need, so we are interested
                    self.log.debug('Interested in "%s" after he got piece %d', conn.getShortRemotePeerAddr(), message[1])
                    conn.setLocalInterest(True)
                    
                    if (not conn.remoteChoked()):
                        #we are already unchoked, spawn some requests!
                        self.log.debug('"%s" unchoked us in the past!', conn.getShortRemotePeerAddr())
                        torrent['requester'].connGotUnchoked(conn)
            
        elif message[0]==5:
            #remotes bitfield
            self.log.debug('Got bitfield from "%s"', conn.getShortRemotePeerAddr())
            torrent = self._getTorrentInfo(conn)
            status = conn.getStatus()
            status.addBitfield(message[1])

            if torrent['ownStatus'].isSeed() and status.isSeed():
                #both seeds, disconnect
                self._removeConnection(connId, "is seed and we are also a seed", False)
            else:
                #check if the peer has something interesting
                if status.hasMatchingGotPieces(self._getTorrentInfo(conn)['ownStatus'].getMissingPieces()):
                    #yep he has
                    self.log.debug('Interested in "%s" after getting bitfield', conn.getShortRemotePeerAddr())
                    conn.setLocalInterest(True)
                
        elif message[0]==6:
            #remote request
            self.log.debug('Got request from "%s" for piece "%d" with offset "%d" and length "%d"',\
                            conn.getShortRemotePeerAddr(), message[1][0], message[1][1], message[1][2])
            dataHandle = self._getTorrentInfo(conn)['storage'].getDataHandle(message[1][0],message[1][1],message[1][2])
            conn.addOutRequest(message[1][0],message[1][1],message[1][2], dataHandle)
            
        elif message[0]==7:
            #got data
            self.log.debug('Got data from "%s": for piece "%d" with offset "%d" and length "%d"',\
                           conn.getShortRemotePeerAddr(), message[1][0], message[1][1], len(message[1][2]))
                        
            #remove request from list
            conn.finishedInRequest(message[1][0], message[1][1], len(message[1][2]))
            
            #notify requester
            torrent = self._getTorrentInfo(conn)
            if torrent['requester'].finishedRequest(message[1][2], conn, message[1][0], message[1][1]):
                #finished to retrieve a whole piece
                self.log.debug('Piece "%d" is finished', message[1][0])
                
                #send have messages
                for connId in torrent['connIds'].copy():
                    conn = self.conns[connId]
                    conn.send(Messages.generateHave(message[1][0]))
                    status = conn.getStatus()
                    
                    if torrent['ownStatus'].isSeed() and status.isSeed():
                        #both seeds, disconnect
                        self._removeConnection(connId, "is seed and we are also a seed", False)
                    
                    else:
                        if conn.localInterested():
                            #we were interested up to now
                            if not status.hasMatchingGotPieces(torrent['ownStatus'].getMissingPieces()):
                                #nothing to request anymore
                                conn.setLocalInterest(False)
                                torrent['requester'].connGotNotInteresting(conn)                 
                            
        elif message[0]==8:
            #cancel
            self.log.debug('Got cancel request from "%s" for piece "%d" with offset "%d" and length "%d"',
                           conn.getShortRemotePeerAddr(), message[1][0], message[1][1], message[1][2])
            conn.delOutRequest(message[1][0], message[1][1], message[1][2])
            
        else:
            self.log.warn('Unmatched message with ID: %d - shouldn\'t reach this point!', message[0])
   

    ##internal functions - thread related
    
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
                recv, send, error = self.connStatus.getSelectSets()
                
                self.lock.release()
                recv, send, error = self.selectFunc(recv, send, error, timeout=0.25)
                self.lock.acquire()
                
                #failed conns
                for connId in error:
                    if connId in self.conns:
                        #conn still exists
                        self._removeConnection(connId, "connection failed")
                    
                    
                #readable conns
                for connId in recv:
                    if connId in self.conns:
                        #conn still exists
                        conn = self.conns[connId]
                        messages = conn.recv()
                        for msgNum, message in messages:
                            if self._checkMessage(conn, msgNum, message):
                                #message is somewhat sane
                                self._handleMessage(connId, conn, message)
                    
                    
                #sendable conns
                for connId in send:
                    if connId in self.conns:
                        #conn still exists
                        self.conns[connId].sendQueuedData() 
            
            self.thread = None
            self.log.info("Stopping")
            self.lock.release()
        except:
            self.log.error('Error in main loop:\n%s', logTraceback())
        
    
    ##external functions - thread related
    
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
        
    
    ##external functions - connections
    
    def addConnection(self, torrentIdent, connSock, direction, remotePeerId):
        self.lock.acquire()
        self._addConnection(torrentIdent, connSock, direction, remotePeerId)
        self.lock.release()
        
        
    def getAllConnections(self, torrentIdent):
        self.lock.acquire()
        assert torrentIdent in self.torrents,'unknown ident!'
        conns = self._getAllConnections(torrentIdent)
        self.lock.release()
        return conns
        
    
    ##external functions - torrents
    
    def addTorrent(self, torrentIdent, torrent, globalStatus, inMeasure, outMeasure, storage, requester):
        self.lock.acquire()
        self._addTorrent(torrentIdent, torrent, globalStatus, inMeasure, outMeasure, storage, requester)
        self.lock.release()
        
        
    def removeTorrent(self, torrentIdent):
        self.lock.acquire()
        self._removeTorrent(torrentIdent)
        self.lock.release()
        
    
    ##external functions - stats
    
    def getStats(self, torrentIdent):
        self.lock.acquire()
        stats = []
        if torrentIdent in self.torrents:
            for conn in self._getAllConnections(torrentIdent):
                stats.append(conn.getStats())
        self.lock.release()
        return stats
