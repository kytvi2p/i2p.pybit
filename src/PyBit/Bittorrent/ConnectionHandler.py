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
            self.log.info('Conn %i: Closing because we are already connected to that peer', connSock.fileno())
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
        
        self.log.info('Conn %i: Closing, reason: %s', conn.fileno(), reason)
        
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
        if message[0] is None:
            #corrupt message
            self.log.warning('Conn %i: Got corrupted message', conn.fileno())
            
        elif message[0] == -1:
            #keepalive
            shouldProcess = True
            
        elif message[0] == 0:
            #remote choke
            if conn.remoteChoked():
                self.log.warning('Conn %i: Got choked and we were already choked!', conn.fileno())
            else:
                shouldProcess = True
            
        elif message[0] == 1:
            #remote unchoke
            if not conn.localInterested():
                self.log.warning('Conn %i: Got unchoked and we were not interested. Allowing it because its common practice - doesn\'t mean that it isn\'t stupid.', conn.fileno())
                shouldProcess = True
            if not conn.remoteChoked():
                self.log.warning('Conn %i: Got unchoked and we were already unchoked!', conn.fileno())
            else:
                shouldProcess = True
                
        elif message[0] == 2:
            #remote interested
            if conn.remoteInterested():
                self.log.warning('Conn %i: Set "interested"-flag and they already told us before!', conn.fileno())
            elif not self._getTorrentInfo(conn)['ownStatus'].hasMatchingGotPieces(conn.getStatus().getMissingPieces()):
                self.log.warning('Conn %i: Set "interested"-flag and we have nothing to send them. What do they want?! - still processing because peers are dumb', conn.fileno())
                shouldProcess = True
            else:
                shouldProcess = True
                
        elif message[0] == 3:
            #remote not interested
            if not conn.remoteInterested():
                self.log.warning('Conn %i: Set "not interested"-flag and they already told us before!', conn.fileno())
            elif conn.getAmountOfOutRequests() > 0:
                self.log.warning('Conn %i: Set "not interested"-flag while a running request existed! Choking them and aborting all running requests!', conn.fileno())
                shouldProcess = True
            else:
                shouldProcess = True
                
        elif message[0] == 4:
            #remote got a new piece
            if not self._getTorrentInfo(conn)['torrent'].isValidPiece(message[1]):
                self.log.warning('Conn %i: Finished piece %i which is not a valid piece ...',
                                 conn.fileno(), message[1])
            elif conn.getStatus().hasPiece(message[1]):
                self.log.warning('Conn %i: Finished piece %i which it already had ...',
                                 conn.fileno(), message[1])
            else:
                shouldProcess = True
                
        elif message[0] == 5:
            #remotes bitfield
            normalLength = self._getTorrentInfo(conn)['torrent'].getTotalAmountOfPieces()
            if not normalLength%8 == 0:
                normalLength += (8 - normalLength%8)
                
            if not normalLength == len(message[1]):
                self.log.warning('Conn %i: Bitfield has the wrong size! (Wanted: %i Got: %i)',
                                 conn.fileno(), normalLength, len(message[1]))
                            
            elif msgNum > 1:
                self.log.warning('Conn %i: Bitfield was received as the %i th message!',
                                 conn.fileno(), msgNum)

            else:
                shouldProcess = True
                
        elif message[0] == 6:
            #remote request
            if not self._getTorrentInfo(conn)['torrent'].isValidRequest(message[1][0], message[1][1], message[1][2]):
                self.log.warning('Conn %i: Got request for piece %i with offset %i and length %i - which is insane ...',
                                 conn.fileno(), message[1][0], message[1][1], message[1][2])
                            
            elif conn.getStatus().hasPiece(message[1][0]):
                self.log.warning('Conn %i: Got request for piece %i which it already has ...',
                                 conn.fileno(), message[1][0])
                            
            elif conn.getAmountOfOutRequests() == 256:
                self.log.warning('Conn %i: Got request for parts of piece %i while there are already 256 requests queued - that greedy bastard!',
                                 conn.fileno(), message[1][0])
                            
            elif message[1][2] > 131072:
                self.log.warning('Conn %i: Got request for piece %i with offset %i and length %i - look at the freakin length!',
                                 conn.fileno(), message[1][0], message[1][1], message[1][2])
                            
            elif conn.localChoked():
                self.log.warning('Conn %i: Got request for piece %i with offset %i and length %i but it is choked - probably just normal sync issues',
                                 conn.fileno(), message[1][0], message[1][1], message[1][2])
                            
            elif conn.hasThisOutRequest(message[1][0], message[1][1], message[1][2]):
                self.log.warning('Conn %i: Got request for piece %i with offset %i and length %i but a request for exactly this is alreaqdy queued!',
                                 conn.fileno(), message[1][0], message[1][1], message[1][2])
                            
            else:
                shouldProcess = True
            
        elif message[0] == 7:
            #got data
            if not conn.hasThisInRequest(message[1][0], message[1][1], len(message[1][2])):
                self.log.warning('Conn %i: Got data for piece %i with offset %i and length %i but thats not what we requested - probably just normal sync issues',
                                 conn.fileno(), message[1][0], message[1][1], len(message[1][2]))
                            
                if conn.localInterested():
                    self._getTorrentInfo(conn)['requester'].makeRequests(conn)
                            
            else:
                shouldProcess = True

        elif message[0] == 8:
            #cancel
            if not conn.hasThisOutRequest(message[1][0],message[1][1],message[1][2]):
                self.log.warning('Conn %i: Canceled request of piece %i with offset %i and length %i but we do not have any such request queued for them - probably just normal sync issues',
                              conn.fileno(), message[1][0], message[1][1], message[1][2])
                
            else:
                shouldProcess = True
        else:
            self.log.warning('Conn %i: Got unknown message with type %i - ignoring it',
                             message[0], conn.fileno())
                        
        return shouldProcess
    

    def _handleMessage(self, connId, conn, message):
        if message[0] == -1:
            #keepalive
            self.log.debug('Conn %i: Got keepalive', connId)
            
        elif message[0] == 0:
            #remote choke
            self.log.debug('Conn %i: Got choked', connId)
            self._getTorrentInfo(conn)['requester'].connGotChoked(conn)
            conn.setRemoteChoke(True)
            
        elif message[0] == 1:
            #remote unchoke
            self.log.debug('Conn %i: Got unchoked', connId)
            conn.setRemoteChoke(False)
            if conn.localInterested():
                #and we are interested - means there should be something requestable
                self._getTorrentInfo(conn)['requester'].connGotUnchoked(conn)  
            
        elif message[0] == 2:
            #remote interested
            self.log.debug('Conn %i: Peer is interested in us', connId)
            conn.setRemoteInterest(True)
            
        elif message[0] == 3:
            #remote not interested
            self.log.debug('Conn %i: Peer is no longer interested in us', connId)
            conn.setRemoteInterest(False)
                
        elif message[0] == 4:
            #remote got a new piece
            self.log.debug('Conn %i: Peer finished piece %i',\
                           connId, message[1])
            torrent = self._getTorrentInfo(conn)
            status = conn.getStatus()
            status.gotPiece(message[1])
            
            if torrent['ownStatus'].isSeed() and status.isSeed():
                #both seeds, disconnect
                self._removeConnection(connId, "is seed and we are also a seed", False)
            
            else:
                if (not conn.localInterested()) and (not torrent['ownStatus'].hasPiece(message[1])):
                    #we were not interested, but now this peer got a piece we need, so we are interested
                    self.log.debug('Conn %i: Interested in peer after he got piece %i', connId, message[1])
                    conn.setLocalInterest(True)
                    
                    if (not conn.remoteChoked()):
                        #we are already unchoked, spawn some requests!
                        self.log.debug('Conn %i: Peer unchoked us in the past!', connId)
                        torrent['requester'].connGotUnchoked(conn)
            
        elif message[0] == 5:
            #remotes bitfield
            self.log.debug('Conn %i: Got bitfield', connId)
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
                    self.log.debug('Conn %i: Interested in peer after getting bitfield', connId)
                    conn.setLocalInterest(True)
                
        elif message[0] == 6:
            #remote request
            self.log.debug('Conn %i: Got request for piece %i with offset %i and length %i',\
                            connId, message[1][0], message[1][1], message[1][2])
            dataHandle = self._getTorrentInfo(conn)['storage'].getDataHandle(message[1][0],message[1][1],message[1][2])
            conn.addOutRequest(message[1][0],message[1][1],message[1][2], dataHandle)
            
        elif message[0] == 7:
            #got data
            self.log.debug('Conn %i: Got data for piece %i with offset %i and length %i',\
                           connId, message[1][0], message[1][1], len(message[1][2]))
                        
            #remove request from list
            conn.finishedInRequest(message[1][0], message[1][1], len(message[1][2]))
            
            #notify requester
            torrent = self._getTorrentInfo(conn)
            if torrent['requester'].finishedRequest(message[1][2], conn, message[1][0], message[1][1]):
                #finished to retrieve a whole piece
                self.log.debug('Piece %i is finished', message[1][0])
                
                #send have messages
                missingPieces = torrent['ownStatus'].getMissingPieces()
                weAreSeed = torrent['ownStatus'].isSeed()
                
                for connId in torrent['connIds'].copy():
                    conn = self.conns[connId]
                    conn.send(Messages.generateHave(message[1][0]))
                    status = conn.getStatus()
                    
                    if weAreSeed and status.isSeed():
                        #both seeds, disconnect
                        self._removeConnection(connId, "is seed and we are also a seed", False)
                    
                    else:
                        if conn.localInterested():
                            #we were interested up to now
                            if not status.hasMatchingGotPieces(missingPieces):
                                #nothing to request anymore
                                conn.setLocalInterest(False)
                                torrent['requester'].connGotNotInteresting(conn)                 
                            
        elif message[0] == 8:
            #cancel
            self.log.debug('Conn %i: Peer canceled request of piece %i with offset %i and length %i',
                           connId, message[1][0], message[1][1], message[1][2])
            conn.delOutRequest(message[1][0], message[1][1], message[1][2])
            
        else:
            self.log.warning('Conn %i: Unmatched message with ID: %d - shouldn\'t reach this point!', connId, message[0])
   

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
