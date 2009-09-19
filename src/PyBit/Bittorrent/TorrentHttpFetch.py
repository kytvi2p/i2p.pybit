"""
Copyright 2009  Blub

TorrentHttpFetch, a class for fetching one torrent using http.
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

##builtin
import threading

##own
from Logger import Logger


class TorrentHttpFetch:
    def __init__(self, config, eventSched, httpRequester, torrentIdent, url, urlStr, resultFunc, resultFuncArgs):
        ##given stuff
        self.config = config
        self.eventSched = eventSched
        self.httpRequester = httpRequester
        self.torrentIdent = torrentIdent
        self.url = url
        self.urlStr = urlStr
        self.resultFunc = resultFunc
        self.resultFuncArgs = resultFuncArgs
        
        ##own stuff
        self.log = Logger('Bt', '%-6s - ', self.torrentIdent)
        
        self.fetchTries = 0
        self.requestId = None
        self.eventId = None
        
        ##status
        self.state = 'stopped'
        self.running = False
        
        ##lock
        self.lock = threading.Lock()
        
        
    ##internal functions - state
    
    def _start(self):
        self.requestId = self.httpRequester.makeRequest(self.url, self.finishedFetch, transferTimeout=120, requestTimeout=300, maxSize=1048576)
        self.fetchTries = 1
        self.state = 'fetching (%i. attempt)' % (self.fetchTries,)
        
        
    def _halt(self):
        if self.requestId is not None:
            self.httpRequester.abortRequest(self.requestId)
            self.requestId = None
            
        if self.eventId is not None:
            self.eventSched.removeEvent(self.eventId)
        
        
    ##external functions - state

    def start(self):
        #called when torrent is started
        self.lock.acquire()
        if not self.running:
            self._start()
            self.running = True
        self.lock.release()
        
        
    def stop(self):
        #called when torrent is stopped
        self.lock.acquire()
        if self.running:
            self._halt()
            self.running = False
            self.state = 'stopped'
        self.lock.release()
        
        
    def shutdown(self):
        #called on shutdown
        self.lock.acquire()
        if self.running:
            self.running = False
            self.state = 'stopped'
        self.lock.release()
        
        
    def remove(self):
        #called when torrent is removed
        self.lock.acquire()
        if self.running:
            self.running = False
            self.state = 'stopped'
        self.lock.release()
        
        
    ##external functions - fetch
    
    def retryFetch(self):
        self.lock.acquire()
        if self.running:
            self.requestId = self.httpRequester.makeRequest(self.url, self.finishedFetch, transferTimeout=120, requestTimeout=300, maxSize=1048576)
            self.fetchTries += 1
            self.state = 'fetching (%i. attempt)' % (self.fetchTries,)
        self.lock.release()
    
    
    def finishedFetch(self, result):
        report = False
        
        #check result
        self.lock.acquire()
        if self.running:
            self.requestId = None
            if result['success']:
                #fetch succeded
                report = True
                self.state = 'fetch succeded (%i. attempt)' % (self.fetchTries,)
            else:
                #fetch failed
                header = result['header']
                if header is None:
                    #transfer failure, retry in 60 secs
                    self.eventId = self.eventSched.scheduleEvent(self.retryFetch, timedelta=60)
                    self.state = 'fetch scheduled (%i. attempt)' % (self.fetchTries + 1,)
                else:
                    #server failure, final
                    self.state = 'fetch failed (result: %s %s)' % (header['code'], header['codeText'])
                    report = True
            if report:
                self.running = False
        self.lock.release()
        
        #report to queue manager if needed
        if report:
            self.resultFunc(result, *self.resultFuncArgs)
        
        
    ##external functions - stats
        
    def getStats(self, wantedStats):
        self.lock.acquire()
        stats = {}
        
        if wantedStats.get('state', False):
            stats['state'] = self.state
        
        #connections
        if wantedStats.get('connections', False):
            stats['connections'] = []
            
        #files
        if wantedStats.get('files', False):
            stats['files'] = []
        
        #peers
        if wantedStats.get('peers', False):
            stats['connectedPeers'] = 0
            stats['knownPeers'] = 0
            
        #progress stats
        if wantedStats.get('progress', False):
            stats['progressBytes'] = 0
            stats['progressPercent'] = 0.0
                    
        #requests
        if wantedStats.get('requests', False):
            stats['requests'] = []
            
        #tracker
        if wantedStats.get('tracker', False):
            stats['tracker'] = []
            
        #transfer stats
        if wantedStats.get('transfer', False):
            stats['inRawBytes'] = 0
            stats['outRawBytes'] = 0
            stats['inPayloadBytes'] = 0
            stats['outPayloadBytes'] = 0
            stats['inRawSpeed'] = 0.0
            stats['outRawSpeed'] = 0.0
            stats['protocolOverhead'] = 0.0
            
        if wantedStats.get('transferAverages', False):
            stats['avgInRawSpeed'] = 0.0
            stats['avgOutRawSpeed'] = 0.0
            stats['avgInPayloadSpeed'] = 0.0
            stats['avgOutPayloadSpeed'] = 0.0
            
        #torrent stats
        if wantedStats.get('torrent', False):
            stats['torrentName'] = self.urlStr
            stats['torrentSize'] = 0
            stats['torrentCreator'] = ''
            stats['torrentCreationDate'] = 0
            stats['torrentComment'] = ''
            stats['torrentHash'] = ''
            stats['trackerAmount'] = 0
            stats['fileAmount'] = 0
            stats['pieceAmount'] = 0
            stats['pieceLength'] = 0
            stats['superSeeding'] = False
            
        self.lock.release()
        return stats
    
    ##external funcs - other
    
    def setState(self, state):
        self.lock.acquire()
        self.state = state
        self.lock.release()