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
        self.torrentEvent = None
        self.announceEvent = None
        self.announceHttpRequests = set()
        
        #tracker - scrape
        self.scrapeEvent = None
        self.scrapeHttpRequests = set()
        
        #tracker - checks
        self.i2pHostChecker = re.compile('^([A-Za-z0-9\-~]{512,512}AAAA)(.i2p){0,1}$')
        
        #tracker - info
        self.trackerInfo = TrackerInfo(self.torrent)
        
        #other
        self.paused = False
        self.stopped = False
        self.log = Logger('TrackerRequester', '%-6s - ', torrentIdent)
        self.lock = threading.Lock()
        
        #init
        self._addConfigCallbacks()
        self._updateScrapeStatus(self.config.get('tracker', 'scrapeTrackers'), self.config.get('tracker', 'scrapeWhileStopped'))
    
    
    ##internal functions - callbacks
    
    def _addConfigCallbacks(self):
        callbackScrapeStatusOptions = (('tracker', 'scrapeTrackers'),
                                       ('tracker', 'scrapeWhileStopped'))
                                    
        self.scrapeStatusCallback = self.config.addCallback(callbackScrapeStatusOptions, self.updateScrapeStatus,
                                                            callType='item-funcArgAll', callWithAllOptions=True)
                                                            
        
    def _removeConfigCallbacks(self):
        self.config.removeCallback(self.scrapeStatusCallback)
        
    
    ##internal functions - announces
        
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
            paras['uploaded'] = str(uploadedBytes)
            paras['downloaded'] = str(downloadedBytes)
            paras['left'] = str(missingBytes)
            paras['ip'] = ownAddr+'.i2p'
            paras['port'] = '6889'
            paras['numwant'] = '100'
            url['parameter'] = paras

            if self.torrentEvent is not None:
                url['event'] = self.torrentEvent
                
            self.log.info('Tracker announce url: "%s"', joinUrl(url))
        return url
    
    
    def _makeAnnounceRequest(self, trackerSet):
        url = self._createAnnounceUrl(trackerSet['url'])
        if url is not None:
            requestId = self.httpRequester.makeRequest(url, self.finishedAnnounceRequest,
                                                       callbackArgs=[trackerSet, self.torrentEvent],
                                                       transferTimeout=self.config.get('http', 'trackerRequestTransferTimeout'),\
                                                       requestTimeout=self.config.get('http', 'trackerRequestTimeout'),\
                                                       maxHeaderSize=self.config.get('http', 'trackerRequestMaxHeaderSize'),\
                                                       maxDataSize=self.config.get('http', 'trackerRequestMaxDataSize'),\
                                                       maxReqTries=2)
            self.announceHttpRequests.add(requestId)
        else:
            self.log.debug("Don't know own address yet, retrying announce in 1 minute")
            self.announceEvent = self.sched.scheduleEvent(self.announce, timedelta=60)
        
    
    def _parseAnnounceResponse(self, trackerSet, data):
        url = trackerSet['logUrl']
        valid = False
        
        try:
            response = bdecode(data)
        except:
            self.log.warn('Failed to parse announce response from tracker "%s":\n%s', logTraceback(), url)
            response = None
        
        
        if response is not None:
            if not isinstance(response, dict):
                #whatever this is, its not a standard response
                self.log.error('Announce response from tracker "%s" is in an unknown format', url)
            else:
                valid = True
                if 'failure reason' in response:
                    #request failed
                    self.log.warn('Announce request to tracker "%s" failed: "%s"', url, str(response['failure reason']))
                else:
                    if 'warning message' in response:
                        #just a warning
                        self.log.warn('Announce request to tracker "%s" got warned: "%s"', url, str(response['warning message']))
                    
                    if not 'peers' in response:
                        #no peers in response
                        self.log.info('Tracker "%s" did not return any peers in its announce response', url)
                    
                    elif not isinstance(response['peers'], list):
                        #probably a compact response - can only be used for IPs, so how should this be used with I2P?
                        self.log.error('Tracker "%s" responded with a compact response to the announce request - not interpretable!', url)
                    
                    elif len(response['peers'])==0:
                        #no peers in response
                        self.log.info('Tracker "%s" did not supply any peers in its announce response', url)
                        
                    else:
                        #something valid
                        ownAddr = self.ownAddrFunc()
                        for peer in response['peers']:
                            #check each peer
                            if not isinstance(peer, dict):
                                #whatever this is, its nothing normal
                                self.log.error('Tracker "%s" supplied peers in an unknown format in its announce response', url)
                            
                            elif not 'ip' in peer:
                                #uhm, a peer without ip?!
                                self.log.error('Tracker "%s" supplied peer data without desintations in its announce response!', url)
                            
                            elif not isinstance(peer['ip'], str):
                                #uh, what kind of destination is this?!
                                self.log.error('Tracker "%s" supplied a peer destination of the type "%s" in its announce response!', url, type(peer['ip']))
                                
                            else:
                                #finally, all checks passed, now parse the peer address
                                parseResult = self.i2pHostChecker.search(peer['ip'])
                                if parseResult is None:
                                    #urgh, address is invalid, all the trouble for nothing
                                    self.log.error('Tracker "%s" returned invalid peer with address "%s" in its announce response', url, peer['ip'])
                                
                                else:
                                    #valid address
                                    peerAddr = parseResult.group(1)
                                    if not peerAddr == ownAddr:
                                        self.log.debug('Tracker "%s" returned valid peer with address "%s" in its announce response', url, peerAddr)
                                        self.peerPool.addPossibleConnections(self.torrentIdent, [peerAddr])
        return valid
    
    
    def _finishedAnnounceRequest(self, response, trackerSet, event):
        self.announceHttpRequests.remove(response['id'])
        success = response['success']
        
        if success:
            #got data
            self.log.debug('Got announce response from tracker "%s"', trackerSet['logUrl'])
            valid = self._parseAnnounceResponse(trackerSet, response['data'])
            
        if success and valid:
            #request was a success
            self.log.debug('Announce request to tracker "%s" succeeded', trackerSet['logUrl'])
            self.trackerInfo.markSuccessful(trackerSet['id'])
            
            if self.config.get('tracker', 'scrapeTrackers') == 'active':
                self._scrapeOneTracker(trackerSet)
            
            if self.paused and event!='stop':
                #got paused - need to send stop event
                self.log.debug("Sending stop event")
                self.announceEvent = self.sched.scheduleEvent(self.announce)
                
            elif self.paused and event=='stop':
                #just finished sending stop event
                self.log.debug("Finished sending stop event")
                self.torrentEvent = None
                
            else:
                #was not a stop event and not paused
                self.log.debug("Next announce request in 60 minutes")
                self.torrentEvent = None
                self.announceEvent = self.sched.scheduleEvent(self.announce, timedelta=3600)
        
        else:
            #request failed
            if 'failureMsg' in response:
                reason = response['failureMsg']
            else:
                reason = 'invalid response'
                
            self.log.debug('Announce request to tracker "%s" failed: %s', trackerSet['logUrl'], reason)
            nextTracker = self.trackerInfo.getNext(trackerSet['id'])
            if nextTracker is None:
                #try again after some time
                if success:
                    self.log.debug("Next announce request in 10 minute")
                    self.announceEvent = self.sched.scheduleEvent(self.announce, timedelta=600)
                else:
                    self.log.debug("Next announce request in 1 minute")
                    self.announceEvent = self.sched.scheduleEvent(self.announce, timedelta=60)
                
            else:
                #try next
                self._makeAnnounceRequest(nextTracker)
        
        
    def _abortAnnounces(self):
        for requestId in self.announceHttpRequests:
            self.httpRequester.abortRequest(requestId)
        self.announceHttpRequests.clear()      
        
    
    ##internal functions - scrapes
        
    def _createScrapeUrl(self, url):
        url = url.copy()
        paras = url.get('parameter', {}).copy()
        paras['info_hash'] = self.torrent.getTorrentHash()
        url['parameter'] = paras
        self.log.info('Tracker scrape url: "%s"', joinUrl(url))
        return url
    
    
    def _makeScrapeRequest(self, trackerSet):
        url = self._createScrapeUrl(trackerSet['scrapeUrl'])
        requestId = self.httpRequester.makeRequest(url, self.finishedScrapeRequest,
                                                   callbackArgs=[trackerSet],
                                                   transferTimeout=self.config.get('http', 'trackerRequestTransferTimeout'),\
                                                   requestTimeout=self.config.get('http', 'trackerRequestTimeout'),\
                                                   maxHeaderSize=self.config.get('http', 'trackerRequestMaxHeaderSize'),\
                                                   maxDataSize=self.config.get('http', 'trackerRequestMaxDataSize'),\
                                                   maxReqTries=2)
        self.scrapeHttpRequests.add(requestId)
        
    
    def _parseScrapeResponse(self, trackerSet, data):
        url = trackerSet['scrapeLogUrl']
        infoHash = self.torrent.getTorrentHash()
        valid = False
        
        try:
            response = bdecode(data)
        except:
            self.log.warn('Failed to parse scrape response from tracker "%s":\n%s', url, logTraceback())
            response = None
        
        
        if response is not None:
            if not isinstance(response, dict):
                #whatever this is, its not a standard response
                self.log.error('Scrape response from tracker "%s" is in an unknown format', url)
            else:
                valid = True
                if 'failure reason' in response:
                    #request failed
                    self.log.warn('Scrape request to tracker "%s" failed: "%s"', url, str(response['failure reason']))
                else:
                    if 'warning message' in response:
                        #just a warning
                        self.log.warn('Scrape request to tracker "%s" got warned: "%s"', url, str(response['warning message']))
                    
                    if not 'files' in response:
                        #files missing
                        self.log.warn('Scrape response from tracker "%s" is incomplete ("file" key is missing)', url)
                    
                    elif not isinstance(response['files'], dict):
                        #invalid format
                        self.log.warn('Scrape response from tracker "%s" is in an unknown format (invalid type "%s" for key "files")', url, type(response['files']))
                        
                    elif not infoHash in response['files']:
                        #missing stats for this torrent
                        self.log.warn('Scrape response from tracker "%s" contains no stats for this torrent', url)
                        
                    elif not isinstance(response['files'][infoHash], dict):
                        #invalid format
                        self.log.warn('Scrape response from tracker "%s" is in an unknown format (invalid type "%s" for torrent stats entry)', url, type(response['files'][infoHash]))
                        
                    else:
                        #ok
                        stats = response['files'][infoHash]
                        
                        #try to get counts
                        seeds = stats.get('complete', 0)
                        if not (isinstance(seeds, int) or isinstance(seeds, long)):
                            self.log.warn('Scrape response from tracker "%s" contains invalid "complete" stats of type "%s"', url, type(seeds))
                            seeds = 0
                            
                        leeches = stats.get('incomplete', 0)
                        if not (isinstance(leeches, int) or isinstance(leeches, long)):
                            self.log.warn('Scrape response from tracker "%s" contains invalid "incomplete" stats of type "%s"', url, type(leeches))
                            leeches = 0
                            
                        downloads = stats.get('downloaded', 0)
                        if not (isinstance(downloads, int) or isinstance(downloads, long)):
                            self.log.warn('Scrape response from tracker "%s" contains invalid "downloaded" stats of type "%s"', url, type(downloads))
                            downloads = 0
                            
                        #report
                        self.log.info('Scrape response from tracker "%s" reported %i seeds, %i leeches and %i finished downloads', url, seeds, leeches, downloads)
                        self.trackerInfo.setScrapeStats(trackerSet['id'], seeds, leeches, downloads)
                    
        return valid
    
    
    def _scrapeOneTracker(self, trackerSet):
        if trackerSet['scrapeUrl'] is None:
            self.log.info('Tracker "%s" - scraping not supported', trackerSet['scrapeLogUrl'])
        else:
            self.log.info('Tracker "%s" - scraping', trackerSet['scrapeLogUrl'])
            self._makeScrapeRequest(trackerSet)
        
    
    def _scrapeAllTracker(self):
        self.log.info('Scraping all tracker')
        trackerSets = self.trackerInfo.getAll()
        for trackerSet in trackerSets:
            self._scrapeOneTracker(trackerSet)
    
    
    def _finishedScrapeRequest(self, response, trackerSet):
        self.scrapeHttpRequests.remove(response['id'])
        success = response['success']
        
        if success:
            #got data
            self.log.debug('Got scrape response from tracker "%s"', trackerSet['logUrl'])
            valid = self._parseScrapeResponse(trackerSet, response['data'])
        
        if not (success and valid):
            if 'failureMsg' in response:
                reason = response['failureMsg']
            else:
                reason = 'invalid response'
                
            self.log.debug('Scrape request to tracker "%s" failed: %s', trackerSet['logUrl'], reason)
            self.trackerInfo.clearScrapeStats(trackerSet['id'])
            
            
    def _abortScrapes(self):
        for requestId in self.scrapeHttpRequests:
            self.httpRequester.abortRequest(requestId)
        self.scrapeHttpRequests.clear()
        
        
    def _updateScrapeStatus(self, scrapeTrackers, scrapeWhileStopped):
        if self.scrapeEvent is None and scrapeTrackers == 'all' and (scrapeWhileStopped or not self.paused) and self.stopped == False:
            #no scrape event but should be scraping all trackers
            self.scrapeEvent = self.sched.scheduleEvent(self.scrape, repeatdelta=3600)
            
        elif self.scrapeEvent is not None and ((not scrapeTrackers == 'all') or (self.paused and not scrapeWhileStopped) or self.stopped):
            #scraping all trackers but should not
            self.sched.removeEvent(self.scrapeEvent)
            self.scrapeEvent = None
            self._abortScrapes()
            self.trackerInfo.clearAllScrapeStats()
            
                
    ##internal functions - status
    
    def _start(self):
        self.torrentEvent = 'start'
        self.paused = False
        self.stopped = False
        if len(self.announceHttpRequests) == 0 and self.announceEvent is None:
            #were completely stopped
            self.announceEvent = self.sched.scheduleEvent(self.announce)
            
        elif self.announceEvent is not None:
            self.sched.rescheduleEvent(self.announceEvent)
            
        self._updateScrapeStatus(self.config.get('tracker', 'scrapeTrackers'), self.config.get('tracker', 'scrapeWhileStopped'))
            
            
    def _pause(self):
        self.torrentEvent = 'stop'
        self.paused = True
        self.stopped = False
        if self.announceEvent is not None:
            self.sched.rescheduleEvent(self.announceEvent)
            
        self._updateScrapeStatus(self.config.get('tracker', 'scrapeTrackers'), self.config.get('tracker', 'scrapeWhileStopped'))
            
            
    def _stop(self):
        self.paused = False
        self.stopped = True
        if self.announceEvent is not None:
            #abort event
            self.sched.removeEvent(self.announceEvent)
            self.announceEvent = None
        
        self.torrentEvent = None
        self._abortAnnounces()
        self._updateScrapeStatus(self.config.get('tracker', 'scrapeTrackers'), self.config.get('tracker', 'scrapeWhileStopped'))
        self._removeConfigCallbacks()
        
        
    ##internal functions - other
    
    def _setEvent(self, event):
        self.torrentEvent = event
        if self.announceEvent is not None:
            self.sched.rescheduleEvent(self.announceEvent)
            
            
    ##external functions - requests
    
    def announce(self):
        self.lock.acquire()
        if self.announceEvent is not None:
            self.log.debug("Announcing")
            self._makeAnnounceRequest(self.trackerInfo.getFirst())
        self.lock.release()
        
        
    def scrape(self):
        self.lock.acquire()
        if self.scrapeEvent is not None:
            self._scrapeAllTracker()
        self.lock.release()
        
        
    def finishedAnnounceRequest(self, response, trackerSet, event):
        self.lock.acquire()
        if response['id'] in self.announceHttpRequests:
            self._finishedAnnounceRequest(response, trackerSet, event)
        self.lock.release()
        
        
    def finishedScrapeRequest(self, response, trackerSet):
        self.lock.acquire()
        if response['id'] in self.scrapeHttpRequests:
            self._finishedScrapeRequest(response, trackerSet)
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
        
        
    ##external functions - config changes
    
    def updateScrapeStatus(self, scrapeTrackers, scrapeWhileStopped):
        self.lock.acquire()
        self._updateScrapeStatus(scrapeTrackers, scrapeWhileStopped)
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