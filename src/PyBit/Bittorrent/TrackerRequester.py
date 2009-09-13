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
from urllib import quote
import logging
import re
import threading

from Bencoding import bdecode

class TrackerRequester:
    def __init__(self, eventScheduler,  peerId, connPool, ownAddrFunc, httpRequester,
                 inMeasure, outMeasure, storage, torrent, torrentIdent):
        #global stuff
        self.sched = eventScheduler
        self.peerId = peerId
        self.connPool = connPool
        self.ownAddrFunc = ownAddrFunc
        self.httpRequester = httpRequester
        
        #torrent dependent stuff
        self.inMeasure = inMeasure
        self.outMeasure = outMeasure
        self.storage = storage
        self.torrent = torrent
        self.torrentIdent = torrentIdent
        
        #tracker
        self.event = None
        self.requestEvent = None
        self.httpRequestId = None
        
        self.i2pHostChecker = re.compile('^([A-Za-z0-9\-~]{512,512}AAAA)(.i2p){0,1}$')
        self.trackerUrlSplitter = re.compile('^http://([A-Za-z0-9\-~]{512,512}AAAA)(.i2p){0,1}(/.+)')
        self.trackerInfos, self.trackerTiers = self._processTrackerList()
        
        #other
        self.paused = False
        self.stopped = False
        self.log = logging.getLogger(torrentIdent+'-TrackerRequester')
        self.lock = threading.Lock()
        
    
    ##internal functions - tracker
    
    def _processTrackerList(self):
        tracker = self.torrent.getTrackerList()
        trackerList = {}
        prioList = []
        
        tierNum = 0
        trackerId = 0
        
        for tier in tracker:
            #tier
            prioList.append([])
            for trackerAddr in tier:
                #single tracker url
                result = self.trackerUrlSplitter.match(trackerAddr)
                assert result is not None, 'invalid tracker url, this should have been checked before!'
                prioList[tierNum].append(trackerId)
                trackerList[trackerId] = {'addr':result.group(1),
                                          'url':result.group(3),
                                          'logUrl':'http://i2p/'+result.group(1)[:10]+'...'+result.group(3),
                                          'tier':tierNum,
                                          'id':trackerId}
            tierNum += 1
        return trackerList, prioList
    
    
    def _getFirstTracker(self):
        return self.trackerInfos[0]
    
    
    def _getNextTracker(self, trackerId):
        tierId = self.trackerInfos[trackerId]['tier']
        tier = self.trackerTiers[tierId]
        place = tier.index(trackerId)
        
        #get next tracker id
        if place < len(tier)-1:
            #just get next tracker from tier
            nextTrackerId = tier[place+1]
        
        elif tierId < len(self.trackerTiers)-1:
            #last of tier, but there are backup tiers
            nextTrackerId = self.trackerTiers[tierId+1][0]
            
        else:
            #the last tracker
            nextTrackerId = None
            
        if nextTrackerId is None:
            #that was the last available tracker
            nextTracker = None
            
        else:
            #get tracker info
            nextTracker = self.trackerInfos[nextTrackerId]
        return nextTracker
    
    
    def _markTrackerSuccessfull(self, trackerId):
        tierId = self.trackerInfos[trackerId]['tier']
        tier = self.trackerTiers[tierId]
        place = tier.index(trackerId)
        
        if place > 0:
            del tier[place]
            tier.insert(0, trackerId)
            
    
    ##internal functions - tracker requests
        
    def _createAnnounceUrl(self, baseUrl):
        downloadedBytes = self.inMeasure.getTotalTransferedPayloadBytes()
        uploadedBytes = self.outMeasure.getTotalTransferedPayloadBytes()
        missingBytes = self.storage.getAmountOfMissingBytes()
        ownAddr = self.ownAddrFunc()
        self.log.debug("Own addr: %s", ownAddr)
        
        url = ''.join((baseUrl,'?',\
              'info_hash=',quote(self.torrent.getTorrentHash()),'&',\
              'peer_id=',quote(self.peerId),'&',\
              'no_peer_id=1&',\
              'port=6881&',
              'uploaded=',str(uploadedBytes),'&',\
              'downloaded=',str(downloadedBytes),'&',\
              'left=',str(missingBytes),'&',\
              'ip=',ownAddr,'.i2p&',\
              'numwant=','100'))

        if self.event is not None:
            url +='&event='+self.event
        self.log.info('Tracker Announce URL: "%s"', url)
        return url
    
    
    def _makeRequest(self, trackerSet):
        url = self._createAnnounceUrl(trackerSet['url'])
        self.httpRequestId = self.httpRequester.makeRequest(trackerSet['addr'], url,
                                                            self.finishedRequest, callbackArgs=[trackerSet['id'], self.event])
                                                            
    
    def _parseResponse(self, trackerSet, data):
        url = trackerSet['logUrl']
        
        self.log.info('Data from Tracker "%s":\n%s', url, data)
        success = False
        try:
            response = bdecode(data)
        except:
            response = None
        
        
        if response is not None:
            if not type(response)==dict:
                #whatever this is, its not a standard response
                self.log.info('Response from tracker "%s" is in an unknown format', url)
            else:
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
                    else:
                        if len(response['peers'])==0:
                            #no peers in response
                            self.log.info('Tracker "%s" did not supply any peers', url)
                        else:
                            if not type(response['peers'])==list:
                                #probably a compact response - can only be used for IPs, so how should this be used with I2P?
                                self.log.info('Tracker "%s" responded with a compact response - not interpretable!', url)
                            else:
                                for peer in response['peers']:
                                    #check each peer
                                    if not type(peer)==dict:
                                        #whatever this is, its nothing normal
                                        self.log.info('Tracker "%s" supplied peers in an unknown format', url)
                                    else:
                                        if not 'ip' in peer:
                                            #uhm, a peer without ip?!
                                            self.log.info('Tracker "%s" supplied a corrupt peer', url)
                                        else:
                                            #finally, all checks passed, now parse the peer address
                                            parseResult = self.i2pHostChecker.search(peer['ip'])
                                            if parseResult is None:
                                                #urgh, address is invalid, all the trouble for nothing
                                                self.log.info('Got invalid peer with address "%s" from tracker', peer['ip'])
                                            
                                            else:
                                                #valid address
                                                success = True
                                                peerAddr = parseResult.group(1)
                                                self.log.debug('Got valid peer with address "%s" from tracker', peerAddr)
                                                self.connPool.addPossibleConnections(self.torrentIdent, [peerAddr])
        return success
    
    
    def _finishedRequest(self, response, trackerId, event):
        trackerSet = self.trackerInfos[trackerId]
        success = response['success']
        
        if success:
            #got data
            self.log.debug('Got data from tracker "%s"', trackerSet['logUrl'])
            success = self._parseResponse(trackerSet, response['data'])
            
        if success:
            #request was a success
            self.log.debug('Request to tracker "%s" succeeded', trackerSet['logUrl'])
            self._markTrackerSuccessfull(trackerId)
            
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
            nextTracker = self._getNextTracker(trackerId)
            if nextTracker is None:
                #try again in 5 mins
                self.log.debug("Next request in 5 minutes")
                self.requestEvent = self.sched.scheduleEvent(self.announce, timedelta=300)
                
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
            self._makeRequest(self._getFirstTracker())
        else:
            self.log.debug("Race condition - ignoring announce")
        self.lock.release()
        
        
    def finishedRequest(self, response, trackerId, event):
        self.lock.acquire()
        self.httpRequestId = None
        if not self.stopped:
            self._finishedRequest(response, trackerId, event)
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