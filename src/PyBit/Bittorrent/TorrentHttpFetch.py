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
from Measure import Measure


class TorrentHttpFetch:
    def __init__(self, config, eventSched, httpRequester, pInMeasure, pOutMeasure, torrentIdent, url, urlStr, resultFunc, resultFuncArgs):
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
        
        #measure
        self.log.debug("Creating measure classes")
        self.inRate = Measure(eventSched, 60, [pInMeasure])
        self.outRate = Measure(eventSched, 60, [pOutMeasure])
        self.inRate.stop()
        
        #requests
        self.fetchTries = 0
        self.requestId = None
        self.eventId = None
        
        #stats
        self.recvBytes = 0
        self.sendBytes = 0
        self.gotData = 0
        
        ##status
        self.state = 'stopped'
        self.running = False
        
        ##lock
        self.lock = threading.Lock()
        
        
    ##internal functions - requesting
    
    def _fetch(self):
        self.requestId = self.httpRequester.makeRequest(self.url, self.finishedFetch,\
                                                        transferTimeout=self.config.get('http', 'torrentFetchTransferTimeout'),\
                                                        requestTimeout=self.config.get('http', 'torrentFetchRequestTimeout'),\
                                                        maxHeaderSize=self.config.get('http', 'torrentFetchMaxHeaderSize'),\
                                                        maxDataSize=self.config.get('http', 'torrentFetchMaxDataSize'))
        self.fetchTries += 1
        self.state = 'fetching (%i. attempt)' % (self.fetchTries,)
        self.recvBytes = 0
        self.sendBytes = 0
        self.gotData = 0
        
        
    ##internal functions - state
        
    def _start(self):
        self.log.debug("Starting transfer measurement")
        self.inRate.start()
        self.outRate.start()
        
        self.log.debug("Starting request")
        self._fetch()
        
        
    def _halt(self):
        self.log.debug("Stopping transfer measurement")
        self.inRate.stop()
        self.outRate.stop()
        
        if self.requestId is not None:
            self.log.debug("Aborting request")
            self.httpRequester.abortRequest(self.requestId)
            self.requestId = None
            
        if self.eventId is not None:
            self.log.debug("Aborting scheduled request")
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
            self._halt()
            self.running = False
            self.state = 'stopped'
        self.lock.release()
        
        
    def remove(self):
        #called when torrent is removed
        self.lock.acquire()
        if self.running:
            self._halt()
            self.running = False
            self.state = 'stopped'
        self.lock.release()
        
        
    ##external functions - fetch
    
    def retryFetch(self):
        self.lock.acquire()
        if self.running:
            self._fetch()
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
                    self.eventId = self.eventSched.scheduleEvent(self.retryFetch, timedelta=self.config.get('http', 'torrentFetchRetryInterval'))
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
        
        #get progress info
        if self.requestId is None:
            progress = None
        else:
            progress = self.httpRequester.getRequestProgress(self.requestId)
            
            #update send bytes
            sendBytes = progress['sendBytes'] - self.sendBytes
            if sendBytes > 0:
                self.sendBytes = progress['sendBytes']
                self.outRate.updateRate(sendBytes)
                
            #update got bytes
            recvBytes = progress['recvBytes'] - self.recvBytes
            if recvBytes > 0:
                self.recvBytes = progress['recvBytes']
                self.inRate.updateRate(recvBytes)
                
            #update payload
            gotPayload = progress['dataSize'] - self.gotData
            if gotPayload > 0:
                self.gotData = progress['dataSize']
                self.inRate.updatePayloadCounter(gotPayload)
        
        
        ##supported stats (at least partially)
        
        #state
        if wantedStats.get('state', False):
            stats['state'] = self.state
        
        #progress stats
        if wantedStats.get('progress', False):
            if progress is not None:
                stats['progressBytes'] = progress['dataSize']
                stats['progressPercent'] = (progress['dataSize'] * 100.0) / max(progress['maxDataSize'], 1.0)
            else:
                stats['progressBytes'] = 0
                stats['progressPercent'] = 0.0
            
        #transfer stats
        if wantedStats.get('transfer', False):
            stats['inRawBytes'] = self.inRate.getTotalTransferedBytes()
            stats['outRawBytes'] = self.outRate.getTotalTransferedBytes()
            stats['inPayloadBytes'] = self.inRate.getTotalTransferedPayloadBytes()
            stats['outPayloadBytes'] = self.outRate.getTotalTransferedPayloadBytes()
            stats['inRawSpeed'] = self.inRate.getCurrentRate()
            stats['outRawSpeed'] = self.outRate.getCurrentRate()
            stats['protocolOverhead'] = (100.0 * (stats['inRawBytes'] + stats['outRawBytes'] - stats['inPayloadBytes'] - stats['outPayloadBytes'])) / max(stats['inPayloadBytes'] + stats['outPayloadBytes'], 1.0)
        
        if wantedStats.get('transferAverages', False):
            stats['avgInRawSpeed'] = self.inRate.getAverageRate() * 1024
            stats['avgOutRawSpeed'] = self.outRate.getAverageRate() * 1024
            stats['avgInPayloadSpeed'] = self.inRate.getAveragePayloadRate() * 1024
            stats['avgOutPayloadSpeed'] = self.outRate.getAveragePayloadRate() * 1024
            
        #torrent stats
        if wantedStats.get('torrent', False):
            if progress is not None:
                stats['torrentSize'] = progress['maxDataSize']
            else:
                stats['torrentSize'] = 0
            stats['torrentName'] = self.urlStr
            stats['torrentCreator'] = ''
            stats['torrentCreationDate'] = 0
            stats['torrentComment'] = ''
            stats['torrentHash'] = ''
            stats['trackerAmount'] = 0
            stats['fileAmount'] = 0
            stats['pieceAmount'] = 0
            stats['pieceLength'] = 0
            stats['superSeeding'] = False
            
            
        ##unsupported stats
        
        #connections
        if wantedStats.get('connections', False):
            stats['connections'] = []
            
        #files
        if wantedStats.get('files', False):
            stats['files'] = []
        
        #peers
        if wantedStats.get('peers', False) or wantedStats.get('connectionAverages', False):
            #general peer stats
            stats['connectedPeers'] = 0
            stats['knownPeers'] = 0
            stats['knownLeeches'] = 0
            stats['knownLeechesPerSeed'] = 0
            stats['knownSeeds'] = 0
            stats['connectedLeeches'] = 0
            stats['connectedSeeds'] = 0
            
            #connection averages
            stats['averagePeerProgress'] = 0.0
            stats['averagePeerPayloadRatio'] = 0.0
            stats['peersWithLocalInterest'] = 0
            stats['connectedLeechesPerSeed'] = 0
            
            #tracker averages
            stats['knownDownloads'] = 0
            

        #pieces
        if wantedStats.get('pieceAverages', False):
            stats['avgPieceAvailability'] = 0.0
            stats['minPieceAvailability'] = 0
            stats['requestedPieceAmount'] = 0
            stats['avgReqPieceAvailability'] = 0.0
            
        #requests
        if wantedStats.get('requests', False):
            stats['requests'] = []
            
        #tracker
        if wantedStats.get('tracker', False):
            stats['tracker'] = []
            
        if wantedStats.get('trackerStatus', False):
            stats['trackerStatus'] = u'None'
            
        self.lock.release()
        return stats
    
    ##external funcs - other
    
    def setState(self, state):
        self.lock.acquire()
        self.state = state
        self.lock.release()