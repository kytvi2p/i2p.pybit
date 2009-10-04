"""
Copyright 2009  Blub

TrackerRequester, a class which can communicate with a bittorrent tracker.
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

from sha import sha
from time import time
import re
import threading

from Bencoding import bdecode
from HttpUtilities import joinUrl, splitUrl
from Logger import Logger
from TrackerInfo import TrackerInfo
from Utilities import logTraceback


class TrackerRequester:
    def __init__(self, config, eventScheduler,  peerId, peerPool, ownAddrFunc, httpRequester,
                 inMeasure, outMeasure, storage, torrent, torrentIdent):
        #global stuff
        self.config = config
        self.sched = eventScheduler
        self.peerId = peerId
        self.peerPool = peerPool
        self.ownAddrFunc = ownAddrFunc
        self.httpRequester = httpRequester
        
        #torrent dependent stuff
        self.inMeasure = inMeasure
        self.outMeasure = outMeasure
        self.storage = storage
        self.torrent = torrent
        self.torrentIdent = torrentIdent
        
        #tracker - announce
        self.event = None
        self.requestEvent = None
        self.httpRequestId = None
        
        #tracker - scrape
        self.scrapeEvent = None
        self.httpScrapeRequests = {}
        
        #tracker - checks
        self.i2pHostChecker = re.compile('^([A-Za-z0-9\-~]{512,512}AAAA)(.i2p){0,1}$')
        
        #tracker - info
        self.trackerInfo = TrackerInfo(self.torrent)
        
        #other
        self.paused = False
        self.stopped = False
        self.log = Logger('TrackerRequester', '%-6s - ', torrentIdent)
        self.lock = threading.Lock()
          
    
    ##internal functions - tracker requests
        
    def _createAnnounceUrl(self, url):
        downloadedBytes = self.inMeasure.getTotalTransferedPayloadBytes()
        uploadedBytes = self.outMeasure.getTotalTransferedPayloadBytes()
        missingBytes = self.storage.getAmountOfMissingBytes()
        ownAddr = self.ownAddrFunc()
        self.log.debug("Own addr: %s", ownAddr)
        
        if ownAddr == '':
            url = None
        else:
            url = url.copy()
            paras = url.get('parameter', {}).copy()
            paras['info_hash'] = self.torrent.getTorrentHash()
            paras['peer_id'] = self.peerId
            paras['port'] = str(6881)
            paras['uploaded'] = str(uploadedBytes)
            paras['downloaded'] = str(downloadedBytes)
            paras['left'] = str(missingBytes)
            paras['ip'] = ownAddr+'.i2p'
            paras['numwant'] = '100'
            url['parameter'] = paras

            if self.event is not None:
                url['event'] = self.event
                
            self.log.info('Tracker Announce URL: "%s"', joinUrl(url))
        return url
    
    
    def _makeRequest(self, trackerSet):
        url = self._createAnnounceUrl(trackerSet['url'])
        if url is not None:
            self.httpRequestId = self.httpRequester.makeRequest(url, self.finishedRequest,
                                                                callbackArgs=[trackerSet, self.event],
                                                                transferTimeout=self.config.get('http', 'trackerRequestTransferTimeout'),\
                                                                requestTimeout=self.config.get('http', 'trackerRequestTimeout'),\
                                                                maxHeaderSize=self.config.get('http', 'trackerRequestMaxHeaderSize'),\
                                                                maxDataSize=self.config.get('http', 'trackerRequestMaxDataSize'))
        else:
            self.log.debug("Don't know own address yet, retrying in 1 minute")
            self.requestEvent = self.sched.scheduleEvent(self.announce, timedelta=60)
        
    
    def _parseResponse(self, trackerSet, data):
        url = trackerSet['logUrl']
        valid = False
        
        try:
            response = bdecode(data)
        except:
            self.log.warn('Failed to parse response from tracker:\n%s', logTraceback())
            response = None
        
        
        if response is not None:
            if not type(response)==dict:
                #whatever this is, its not a standard response
                self.log.error('Response from tracker "%s" is in an unknown format', url)
            else:
                valid = True
                if 'failure reason' in response:
                    #request failed
                    self.log.warn('Request to Tracker "%s" failed: "%s"', url, str(response['failure reason']))
                else:
                    if 'warning message' in response:
                        #just a warning
                        self.log.warn('Request to Tracker "%s" got warned: "%s"', url, str(response['warning message']))
                    
                    if not 'peers' in response:
                        #no peers in response
                        self.log.info('Tracker "%s" did not supply any peers', url)
                    
                    elif not type(response['peers'])==list:
                        #probably a compact response - can only be used for IPs, so how should this be used with I2P?
                        self.log.error('Tracker "%s" responded with a compact response - not interpretable!', url)
                    
                    elif len(response['peers'])==0:
                        #no peers in response
                        self.log.info('Tracker "%s" did not supply any peers', url)
                        
                    else:
                        #something valid
                        ownAddr = self.ownAddrFunc()
                        for peer in response['peers']:
                            #check each peer
                            if not type(peer)==dict:
                                #whatever this is, its nothing normal
                                self.log.error('Tracker "%s" supplied peers in an unknown format', url)
                            
                            elif not 'ip' in peer:
                                #uhm, a peer without ip?!
                                self.log.error('Tracker "%s" supplied peer data without IPs!', url)
                            else:
                                #finally, all checks passed, now parse the peer address
                                parseResult = self.i2pHostChecker.search(peer['ip'])
                                if parseResult is None:
                                    #urgh, address is invalid, all the trouble for nothing
                                    self.log.error('Got invalid peer with address "%s" from tracker', peer['ip'])
                                
                                else:
                                    #valid address
                                    peerAddr = parseResult.group(1)
                                    if not peerAddr == ownAddr:
                                        self.log.debug('Got valid peer with address "%s" from tracker', peerAddr)
                                        self.peerPool.addPossibleConnections(self.torrentIdent, [peerAddr])
        return valid
    
    
    def _finishedRequest(self, response, trackerSet, event):
        success = response['success']
        
        if success:
            #got data
            self.log.debug('Got data from tracker "%s"', trackerSet['logUrl'])
            valid = self._parseResponse(trackerSet, response['data'])
            
        if success and valid:
            #request was a success
            self.log.debug('Request to tracker "%s" succeeded', trackerSet['logUrl'])
            self.trackerInfo.markSuccessful(trackerSet['id'])
            
            if self.paused and event!='stop':
                #got paused - need to send stop event
                self.log.debug("Sending stop event")
                self.requestEvent = self.sched.scheduleEvent(self.announce)
                
            elif self.paused and event=='stop':
                #just finished sending stop event
                self.log.debug("Finished sending stop event")
                self.event = None
                
            else:
                #was not a stop event and not paused
                self.log.debug("Next request in 60 minutes")
                self.event = None
                self.requestEvent = self.sched.scheduleEvent(self.announce, timedelta=3600)
        
        else:
            #request failed
            if 'failureMsg' in response:
                reason = response['failureMsg']
            else:
                reason = 'invalid response'
                
            self.log.debug('Request to tracker "%s" failed: %s', trackerSet['logUrl'], reason)
            nextTracker = self.trackerInfo.getNext(trackerSet['id'])
            if nextTracker is None:
                #try again after some time
                if success:
                    self.log.debug("Next request in 10 minute")
                    self.requestEvent = self.sched.scheduleEvent(self.announce, timedelta=600)
                else:
                    self.log.debug("Next request in 1 minute")
                    self.requestEvent = self.sched.scheduleEvent(self.announce, timedelta=60)
                
            else:
                #try next
                self._makeRequest(nextTracker)
                
                
    ##internal functions - status
    
    def _start(self):
        self.event = 'start'
        self.paused = False
        self.stopped = False
        if self.httpRequestId is None and self.requestEvent is None:
            #were completely stopped
            self.requestEvent = self.sched.scheduleEvent(self.announce)
            
        elif self.requestEvent is not None:
            self.sched.rescheduleEvent(self.requestEvent)
            
            
    def _pause(self):
        self.event = 'stop'
        self.paused = True
        self.stopped = False
        if self.requestEvent is not None:
            self.sched.rescheduleEvent(self.requestEvent)
            
            
    def _stop(self):
        self.paused = False
        self.stopped = True
        if self.requestEvent is not None:
            #abort event
            self.sched.removeEvent(self.requestEvent)
            self.requestEvent = None
            
        elif self.httpRequestId is not None:
            self.httpRequester.abortRequest(self.httpRequestId)
            self.httpRequestId = None
            
        self.event = None
            
    
    ##internal functions - other
    
    def _setEvent(self, event):
        self.event = event
        if self.requestEvent is not None:
            self.sched.rescheduleEvent(self.requestEvent)
            
            
    ##external functions - requests
    
    def announce(self):
        self.lock.acquire()
        self.requestEvent = None
        if not self.stopped:
            self.log.debug("Announcing")
            self._makeRequest(self.trackerInfo.getFirst())
        else:
            self.log.debug("Race condition - ignoring announce")
        self.lock.release()
        
        
    def finishedRequest(self, response, trackerSet, event):
        self.lock.acquire()
        self.httpRequestId = None
        if not self.stopped:
            self._finishedRequest(response, trackerSet, event)
        self.lock.release()
        
    
    ##external functions - status
    
    def start(self):
        self.lock.acquire()
        self._start()
        self.lock.release()
        
        
    def pause(self):
        self.lock.acquire()
        self._pause()
        self.lock.release()
        
        
    def stop(self):
        self.lock.acquire()
        self._stop()
        self.lock.release()
        
    
    ##external functions - other
    
    def setEvent(self, event):
        self.lock.acquire()
        self._setEvent(event)
        self.lock.release()
        
        
    def getStats(self):
        self.lock.acquire()
        stats = self.trackerInfo.getStats()
        self.lock.release()
        return stats