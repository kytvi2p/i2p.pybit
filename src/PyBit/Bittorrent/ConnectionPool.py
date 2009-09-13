"""
Copyright 2009  Blub

ConnectionPool, a class which keeps track of active connections and known peers.
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

from collections import deque, defaultdict
from time import time
import threading

class ConnectionPool:
    def __init__(self):
        self.currentConns = defaultdict(dict)
        self.possibleConns = defaultdict(dict)
        
        self.lock = threading.Lock()
        
        
    def addPossibleConnections(self, torrentIdent, remoteAddrs):
        self.lock.acquire()
        posConns = self.possibleConns[torrentIdent]
        curConns = self.currentConns[torrentIdent]
        
        for remoteAddr in remoteAddrs:
            if not (remoteAddr in posConns or remoteAddr in curConns):
                posConns[remoteAddr] = {'connectTries':0,
                                        'addTime':time()}
        self.lock.release()
                                        
                                        
    def getPossibleConnections(self, torrentIdent, num, exclude):
        self.lock.acquire()
        addrs = deque()
        addrCount = 0
        for remoteAddr in self.possibleConns[torrentIdent].iterkeys():
            if remoteAddr not in exclude:
                addrs.append(remoteAddr)
                addrCount += 1
                if addrCount >= num:
                    break
                
        self.lock.release()
        return addrs
                


    def establishedConnection(self, torrentIdent, remoteAddr):
        self.lock.acquire()
        posConns = self.possibleConns[torrentIdent]
        curConns = self.currentConns[torrentIdent]
        
        if remoteAddr in posConns:
            #known peer, remove from possible conns
            peer = posConns[remoteAddr]
            del posConns[remoteAddr]
            
            #modify stats
            peer['connectTries'] = 0
            
            #add to current conns
            assert remoteAddr not in curConns,'possible conn but already connected?!'
            curConns[remoteAddr] = peer
            success = True
            
        elif remoteAddr in curConns:
            #known Peer but already connected
            success = False
            
        else:
            #unknown Peer
            curConns[remoteAddr] = {'connectTries':0,
                                    'addTime':time()}
            success = True
        
        self.lock.release()
        return success
    
    
    
    def lostConnection(self, torrentIdent, remoteAddr, keepInPool=True):
        self.lock.acquire()
        #called if a working connection fails
        posConns = self.possibleConns[torrentIdent]
        curConns = self.currentConns[torrentIdent]
        
        #remove peer from current conns
        peer = curConns[remoteAddr]
        del curConns[remoteAddr]
        
        peer['addTime'] = time()
        
        #add to possible conns
        if keepInPool:
            posConns[remoteAddr] = peer
        
        self.lock.release()
        
    
    def failedToConnect(self, torrentIdent, remoteAddr):
        self.lock.acquire()
        #called if a connect attempt failed
        posConns = self.possibleConns[torrentIdent]
        curConns = self.currentConns[torrentIdent]
        
        if remoteAddr in posConns:
            peer = posConns[remoteAddr]
            
            peer['connectTries'] += 1
            
            if peer['connectTries'] >=5 or time()-peer['addTime'] > 300:
                #its no longer worth it to keep this peer
                del posConns[remoteAddr]
        else:
            assert remoteAddr in curConns, 'neither possible nor connected?!'
            
        self.lock.release()
        
        
    def clear(self, torrentIdent):
        self.lock.acquire()
        if torrentIdent in self.currentConns:
            del self.currentConns[torrentIdent]
        if torrentIdent in self.possibleConns:
            del self.possibleConns[torrentIdent]
        self.lock.release()
        
        
    def stop(self):
        self.lock.acquire()
        
        
    def getStats(self, torrentIdent):
        self.lock.acquire()
        stats = {}
        if torrentIdent in self.possibleConns:
            #known torrent
            stats['connectedPeers'] = len(self.currentConns[torrentIdent])
            stats['knownPeers'] = stats['connectedPeers'] + len(self.possibleConns[torrentIdent])
            
        else:
            #unknown, default to 0
            stats['connectedPeers'] = 0
            stats['knownPeers'] = 0
        self.lock.release()
        return stats