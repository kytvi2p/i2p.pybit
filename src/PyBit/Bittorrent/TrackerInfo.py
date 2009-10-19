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
        self.trackerInfos, self.trackerTiers = self._create()
        self.activeTracker = None
        self.lock = threading.Lock()
        
    
    ##internal functions - tracker
    
    def _create(self):
        tracker = self.torrent.getTrackerList()
        trackerList = {}
        prioList = []
        
        tierNum = 0
        trackerId = 0
        
        for tier in tracker:
            #tier
            prioList.append([])
            for trackerUrl in tier:
                #single tracker url
                prioList[tierNum].append(trackerId)
                
                #info
                trackerInfo = {'url':splitUrl(trackerUrl),
                               'logUrl':trackerUrl,
                               'tier':tierNum,
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
                trackerInfo['scrapeLogUrl'] = joinUrl(trackerInfo['scrapeUrl'])
                trackerList[trackerId] = trackerInfo
                
                #counts
                self.trackerSeedCounts[trackerId] = 0
                self.trackerLeechCounts[trackerId] = 0
                self.trackerDownloadCounts[trackerId] = 0
                
                trackerId += 1
            tierNum += 1
            
        return trackerList, prioList
    
    
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
    
    
    def _getAllTracker(self):
        return [deepcopy(info) for info in self.trackerInfos.itervalues()]
    
        
    def _getFirstTracker(self):
        return deepcopy(self.trackerInfos[0])
    
    
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
    
    
    ##external functions - tracker
    
    def getAll(self):
        with self.lock:
            return self._getAllTracker()
        
    
    def getFirst(self):
        with self.lock:
            return self._getFirstTracker()
        
    
    def getNext(self, trackerId):
        with self.lock:
            return self._getNextTracker(trackerId)
    
    
    ##external functions - announce
    
    def setAnnounceTry(self, trackerId):
        with self.lock:
            self._setAnnounceTry(trackerId)
            
            
    def setAnnounceFailure(self, trackerId):
        with self.lock:
            self._setAnnounceFailure(trackerId)
            
    
    def setAnnounceSuccess(self, trackerId):
        with self.lock:
            self._setAnnounceSuccess(trackerId)
        
    
    ##external functions - scrape
    
    def setScrapeTry(self, trackerId):
        with self.lock:
            self._setScrapeTry(trackerId)
    
    
    def setScrapeSuccess(self, trackerId):
        with self.lock:
            self._setScrapeSuccess(trackerId)
            
    
    def setScrapeStats(self, trackerId, seeds, leeches, downloads):
        with self.lock:
            self._setTrackerScrapeStats(trackerId, seeds, leeches, downloads)
        
        
    def clearScrapeStats(self, trackerId):
        with self.lock:
            self._clearTrackerScrapeStats(trackerId)
            
        
    def clearAllScrapeStats(self):
        with self.lock:
            self._clearAllTrackerScrapeStats()
        
    
    ##external functions - other
    
    def getStats(self):
        with self.lock:
            stats = []
            for tierNum, tier in enumerate(self.trackerTiers):
                for trackerNum, trackerId in enumerate(tier):
                    trackerSet = self.trackerInfos[trackerId]
                    stats.append({'tier':tierNum + 1,
                                  'tierPos':trackerNum + 1,
                                  'trackerUrl':trackerSet['logUrl'],
                                  'trackerId':trackerId,
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
                                  'downloads':self.trackerDownloadCounts[trackerId]})
            return stats