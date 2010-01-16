"""
Copyright 2009  Blub

TrackerInfo, a class which handles all information regarding trackers.
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
from __future__ import with_statement
from copy import deepcopy
from time import time
import threading

##own
from HttpUtilities import joinUrl, splitUrl




class TrackerInfo:
    def __init__(self, torrent):
        self.torrent = torrent
        self.trackerSeedCounts = {}
        self.trackerLeechCounts = {}
        self.trackerDownloadCounts = {}
        
        self.trackerInfos = {}
        self.trackerTiers = []
        self._initTrackerInfo()
        
        self.activeTracker = None
        self.lock = threading.Lock()
        
    
    ##internal functions - init
    
    def _initTrackerInfo(self):
        tracker = self.torrent.getTrackerList()
        self.trackerInfos = {}
        self.trackerTiers = []
        
        tierIdx = 0
        trackerId = 0
        
        for tier in tracker:
            #tier
            self.trackerTiers.append([])
            for trackerUrl in tier:
                #single tracker url
                self.trackerTiers[tierIdx].append(trackerId)
                
                #info
                self.trackerInfos[trackerId] = self._genTrackerInfo(tierIdx, trackerId, trackerUrl)
                
                #counts
                self.trackerSeedCounts[trackerId] = 0
                self.trackerLeechCounts[trackerId] = 0
                self.trackerDownloadCounts[trackerId] = 0
                
                trackerId += 1
            tierIdx += 1
    
    
    def _getScrapeUrl(self, trackerUrl):
        splitPath = trackerUrl['path'].split('/')
        if not splitPath[-1].startswith('announce'):
            #does not support scrape requests
            scrapeUrl = None
        else:
            #supports scrape
            scrapeUrl = trackerUrl.copy()
            splitPath[-1] = 'scrape'+splitPath[-1][8:]
            scrapeUrl['path'] = '/'.join(splitPath)
        return scrapeUrl
    
    
    def _genTrackerInfo(self, tierIdx, trackerId, trackerUrl):
        trackerInfo = {'url':splitUrl(trackerUrl),
                       'logUrl':trackerUrl,
                       'tier':tierIdx,
                       'id':trackerId,
                       'announceTryCount':0,
                       'announceTryTime':None,
                       'announceSuccessCount':0,
                       'announceSuccessTime':None,
                       'scrapeTryCount':0,
                       'scrapeTryTime':None,
                       'scrapeSuccessCount':0,
                       'scrapeSuccessTime':None}
        trackerInfo['scrapeUrl'] = self._getScrapeUrl(trackerInfo['url'])
        if trackerInfo['scrapeUrl'] is None:
            trackerInfo['scrapeLogUrl'] = ''
        else:
            trackerInfo['scrapeLogUrl'] = joinUrl(trackerInfo['scrapeUrl'])
        return trackerInfo
    
    
    ##internal functions - general
    
    def _getAllTracker(self):
        return [deepcopy(info) for info in self.trackerInfos.itervalues()]
    
        
    def _getFirstTracker(self):
        if len(self.trackerInfos) > 0:
            trackerSet = deepcopy(self.trackerInfos[0])
        else:
            trackerSet = None
        return trackerSet
    
    
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
            nextTracker = deepcopy(self.trackerInfos[nextTrackerId])
            
        return nextTracker
    
    
    ##internal functions - announce
    
    def _setAnnounceTry(self, trackerId):
        trackerSet = self.trackerInfos[trackerId]
        trackerSet['announceTryCount'] += 1
        trackerSet['announceTryTime'] = time()
        
        
    def _setAnnounceFailure(self, trackerId):
        if trackerId == self.activeTracker:
            self.activeTracker = None
        
    
    def _setAnnounceSuccess(self, trackerId):
        trackerSet = self.trackerInfos[trackerId]
        trackerSet['announceSuccessCount'] += 1
        trackerSet['announceSuccessTime'] = time()
        self.activeTracker = trackerId
        
        tierId = trackerSet['tier']
        tier = self.trackerTiers[tierId]
        place = tier.index(trackerId)
        
        if place > 0:
            del tier[place]
            tier.insert(0, trackerId)
            
    
    ##internal functions - scrape
    
    def _setScrapeTry(self, trackerId):
        trackerSet = self.trackerInfos[trackerId]
        trackerSet['scrapeTryCount'] += 1
        trackerSet['scrapeTryTime'] = time()
        
        
    def _setScrapeSuccess(self, trackerId):
        trackerSet = self.trackerInfos[trackerId]
        trackerSet['scrapeSuccessCount'] += 1
        trackerSet['scrapeSuccessTime'] = time()
        
    
    def _setTrackerScrapeStats(self, trackerId, seeds, leeches, downloads):
        self.trackerSeedCounts[trackerId] = seeds
        self.trackerLeechCounts[trackerId] = leeches
        self.trackerDownloadCounts[trackerId] = downloads
        
        
    def _clearTrackerScrapeStats(self, trackerId):
        self.trackerSeedCounts[trackerId] = 0
        self.trackerLeechCounts[trackerId] = 0
        self.trackerDownloadCounts[trackerId] = 0
            
        
    def _clearAllTrackerScrapeStats(self):
        for trackerId in self.trackerSeedCounts.keys():
            self.trackerSeedCounts[trackerId] = 0
            self.trackerLeechCounts[trackerId] = 0
            self.trackerDownloadCounts[trackerId] = 0
            
            
    ##internal functions - stats
    
    def _getStats(self):
        stats = {}
        trackerPrio = len(self.trackerInfos)
        for tierNum, tier in enumerate(self.trackerTiers):
            for trackerNum, trackerId in enumerate(tier):
                trackerSet = self.trackerInfos[trackerId]
                stats[trackerId] = {'tier':tierNum + 1,
                                    'tierPos':trackerNum + 1,
                                    'trackerUrl':trackerSet['logUrl'],
                                    'trackerId':trackerId,
                                    'trackerPrio':trackerPrio,
                                    'active':(trackerId == self.activeTracker),
                                    'announceTryCount':trackerSet['announceTryCount'],
                                    'announceTryTime':trackerSet['announceTryTime'],
                                    'announceSuccessCount':trackerSet['announceSuccessCount'],
                                    'announceSuccessTime':trackerSet['announceSuccessTime'],
                                    'scrapeTryCount':trackerSet['scrapeTryCount'],
                                    'scrapeTryTime':trackerSet['scrapeTryTime'],
                                    'scrapeSuccessCount':trackerSet['scrapeSuccessCount'],
                                    'scrapeSuccessTime':trackerSet['scrapeSuccessTime'],
                                    'seeds':self.trackerSeedCounts[trackerId],
                                    'leeches':self.trackerLeechCounts[trackerId],
                                    'downloads':self.trackerDownloadCounts[trackerId]}
                trackerPrio -= 1
        return stats
    
    
    ##internal functions - modifying
    
    def _getTrackerInfo(self):
        stats = self._getStats()
        trackerInfo = []
        for tierIdx in xrange(0, len(self.trackerTiers)):
            tier = self.trackerTiers[tierIdx]
            trackerInfo.append([stats[trackerId] for trackerId in tier])
        return trackerInfo
    
    
    def _setTrackerInfo(self, newTrackerInfos):
        #create set of old trackers
        oldTrackerIds = set(self.trackerInfos.iterkeys())
        
        #create new tier list, add/update/remove trackers while doing so
        allTrackerIds = set()
        self.trackerTiers = []
        
        for tierIdx, tier in enumerate(tier for tier in newTrackerInfos if len(tier) > 0):
            #process one tier
            trackerIds = []
            for tracker in tier:
                #process one tracker
                trackerId = tracker['trackerId']
                allTrackerIds.add(trackerId)
                trackerIds.append(trackerId)
                
                if not trackerId in self.trackerInfos:
                    #new tracker
                    self.trackerInfos[trackerId] = self._genTrackerInfo(tierIdx, trackerId, tracker['trackerUrl'])
                    self.trackerSeedCounts[trackerId] = 0
                    self.trackerLeechCounts[trackerId] = 0
                    self.trackerDownloadCounts[trackerId] = 0
                else:
                    #old tracker
                    oldTracker = self.trackerInfos[trackerId]
                    oldTracker['tier'] = tierIdx
                    oldTracker['url'] = splitUrl(tracker['trackerUrl'])
                    oldTracker['logUrl'] = tracker['trackerUrl']
                    
            self.trackerTiers.append(trackerIds)
        
        #remove old trackers which are not in any tier
        for trackerId in oldTrackerIds.difference(allTrackerIds):
            del self.trackerInfos[trackerId]
            del self.trackerSeedCounts[trackerId]
            del self.trackerLeechCounts[trackerId]
            del self.trackerDownloadCounts[trackerId]
            
    
    ##external functions - general
    
    def getAll(self):
        with self.lock:
            return self._getAllTracker()
        
    
    def getFirst(self):
        with self.lock:
            return self._getFirstTracker()
        
    
    def getNext(self, trackerId):
        with self.lock:
            if trackerId in self.trackerInfos:
                trackerSet = self._getNextTracker(trackerId)
            else:
                trackerSet = self._getFirstTracker()
            return trackerSet
    
    
    ##external functions - announce
    
    def setAnnounceTry(self, trackerId):
        with self.lock:
            if trackerId in self.trackerInfos:
                self._setAnnounceTry(trackerId)
            
            
    def setAnnounceFailure(self, trackerId):
        with self.lock:
            if trackerId in self.trackerInfos:
                self._setAnnounceFailure(trackerId)
            
    
    def setAnnounceSuccess(self, trackerId):
        with self.lock:
            if trackerId in self.trackerInfos:
                self._setAnnounceSuccess(trackerId)
        
    
    ##external functions - scrape
    
    def setScrapeTry(self, trackerId):
        with self.lock:
            if trackerId in self.trackerInfos:
                self._setScrapeTry(trackerId)
    
    
    def setScrapeSuccess(self, trackerId):
        with self.lock:
            if trackerId in self.trackerInfos:
                self._setScrapeSuccess(trackerId)
            
    
    def setScrapeStats(self, trackerId, seeds, leeches, downloads):
        with self.lock:
            if trackerId in self.trackerInfos:
                self._setTrackerScrapeStats(trackerId, seeds, leeches, downloads)
        
        
    def clearScrapeStats(self, trackerId):
        with self.lock:
            if trackerId in self.trackerInfos:
                self._clearTrackerScrapeStats(trackerId)
            
        
    def clearAllScrapeStats(self):
        with self.lock:
            self._clearAllTrackerScrapeStats()
            
    ##external functions - modifying
    
    def getTrackerInfo(self):
        with self.lock:
            return self._getTrackerInfo()
        
    
    def setTrackerInfo(self, newTrackerInfos):
        with self.lock:
            if newTrackerInfos is not None:
                self._setTrackerInfo(newTrackerInfos)
            else:
                self._initTrackerInfo()
        
    
    ##external functions - other
    
    def getStats(self):
        with self.lock:
            stats = self._getStats().values()
            return stats