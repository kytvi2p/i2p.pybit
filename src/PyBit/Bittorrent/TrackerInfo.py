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
        
        self.trackerInfos = {}
        self.trackerTiers = []
        self._initTrackerInfo()
        
        self.activeTracker = None
        self.lock = threading.Lock()
        
        
    ##internal functions - tracker - init
    
    def _initTrackerInfo(self):
        self._createTrackerInfo()
        
    
    def _createTrackerInfo(self):
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
                
                trackerId += 1
            tierIdx += 1
    
    
    ##internal functions - tracker - general
    
    def _getScrapeUrl(self, trackerUrl):
        splitPath = trackerUrl['path'].split('/')
        if not splitPath[-1].startswith('announce'):
            #does not support scrape requests
            scrapeUrl = None
            scrapeLogUrl = ''
        else:
            #supports scrape
            scrapeUrl = trackerUrl.copy()
            splitPath[-1] = 'scrape'+splitPath[-1][8:]
            scrapeUrl['path'] = '/'.join(splitPath)
            scrapeLogUrl = joinUrl(scrapeUrl)
        return scrapeUrl, scrapeLogUrl
    
    
    def _genTrackerInfo(self, tierIdx, trackerId, trackerUrl):
        trackerInfo = {'url':splitUrl(trackerUrl),
                       'logUrl':trackerUrl,
                       'tier':tierIdx,
                       'id':trackerId,
                       'announceTryCount':0,
                       'announceTryTime':None,
                       'announceSuccessCount':0,
                       'announceSuccessTime':None,
                       'lastAnnounceResult':u'None',
                       'scrapeTryCount':0,
                       'scrapeTryTime':None,
                       'scrapeSuccessCount':0,
                       'scrapeSuccessTime':None,
                       'seedCount':0,
                       'leechCount':0,
                       'downloadCount':0}
        trackerInfo['scrapeUrl'], trackerInfo['scrapeLogUrl'] = self._getScrapeUrl(trackerInfo['url'])
        return trackerInfo
    
    
    ##internal functions - tracker - info
    
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
    
    
    ##internal functions - tracker - announce
    
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
            
            
    def _setAnnounceResult(self, trackerId, result):
        trackerSet = self.trackerInfos[trackerId]
        trackerSet['lastAnnounceResult'] = result
            
    
    ##internal functions - scrape - announce
    
    def _setScrapeTry(self, trackerId):
        trackerSet = self.trackerInfos[trackerId]
        trackerSet['scrapeTryCount'] += 1
        trackerSet['scrapeTryTime'] = time()
        
        
    def _setScrapeSuccess(self, trackerId):
        trackerSet = self.trackerInfos[trackerId]
        trackerSet['scrapeSuccessCount'] += 1
        trackerSet['scrapeSuccessTime'] = time()
        
    
    def _setTrackerScrapeStats(self, trackerId, seeds, leeches, downloads):
        trackerInfo = self.trackerInfos[trackerId]
        trackerInfo['seedCount'] = seeds
        trackerInfo['leechCount'] = leeches
        trackerInfo['downloadCount'] = downloads
        
        
    def _clearTrackerScrapeStats(self, trackerId):
        trackerInfo = self.trackerInfos[trackerId]
        trackerInfo['seedCount'] = 0
        trackerInfo['leechCount'] = 0
        trackerInfo['downloadCount'] = 0
            
        
    def _clearAllTrackerScrapeStats(self):
        for trackerId in self.trackerInfo.keys():
            trackerInfo = self.trackerInfos[trackerId]
            trackerInfo['seedCount'] = 0
            trackerInfo['leechCount'] = 0
            trackerInfo['downloadCount'] = 0
            
            
    ##internal functions - tracker - stats
    
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
                                    'lastAnnounceResult':trackerSet['lastAnnounceResult'],
                                    'scrapeTryCount':trackerSet['scrapeTryCount'],
                                    'scrapeTryTime':trackerSet['scrapeTryTime'],
                                    'scrapeSuccessCount':trackerSet['scrapeSuccessCount'],
                                    'scrapeSuccessTime':trackerSet['scrapeSuccessTime'],
                                    'seeds':trackerSet['seedCount'],
                                    'leeches':trackerSet['leechCount'],
                                    'downloads':trackerSet['downloadCount']}
                trackerPrio -= 1
        return stats
    
    
    ##internal functions - tracker - modifying
    
    def _getTrackerInfo(self):
        stats = self._getStats()
        trackerInfo = []
        for tierIdx in xrange(0, len(self.trackerTiers)):
            tier = self.trackerTiers[tierIdx]
            trackerInfo.append([stats[trackerId] for trackerId in tier])
        return trackerInfo
    
    
    def _setTrackerInfo(self, newTrackerInfos):
        if newTrackerInfos is None:
            #restore defaults
            self._createTrackerInfo()
        else:
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
                    else:
                        #old tracker
                        oldTracker = self.trackerInfos[trackerId]
                        oldTracker['tier'] = tierIdx
                        oldTracker['url'] = splitUrl(tracker['trackerUrl'])
                        oldTracker['logUrl'] = tracker['trackerUrl']
                        oldTracker['scrapeUrl'], oldTracker['scrapeLogUrl'] = self._getScrapeUrl(oldTracker['url'])
                        
                self.trackerTiers.append(trackerIds)
            
            #remove old trackers which are not in any tier
            for trackerId in oldTrackerIds.difference(allTrackerIds):
                del self.trackerInfos[trackerId]
                
    
    ##external functions - tracker - general
    
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
    
    
    ##external functions - tracker - announce
    
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
                
                
    def setAnnounceResult(self, trackerId, result):
        with self.lock:
            if trackerId in self.trackerInfos:
                self._setAnnounceResult(trackerId, result)
        
    
    ##external functions - tracker - scrape
    
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
            
    ##external functions - tracker - modifying
    
    def getTrackerInfo(self):
        with self.lock:
            return self._getTrackerInfo()
        
    
    def setTrackerInfo(self, newTrackerInfos):
        with self.lock:
            self._setTrackerInfo(newTrackerInfos)
        
    
    ##external functions - tracker - stats
    
    def getStats(self, **kwargs):
        with self.lock:
            stats = {}
            
            if kwargs.get('trackerDetails', False):
                #generate detailed per tracker stats
                stats['tracker'] = self._getStats().values()
            
            if kwargs.get('trackerSummary', False):
                #generate summarised tracker stats
                stats['knownSeeds'] = max(trackerInfo['seedCount'] for trackerInfo in self.trackerInfos.itervalues())
                stats['knownLeeches'] = max(trackerInfo['leechCount'] for trackerInfo in self.trackerInfos.itervalues())
                stats['knownDownloads'] = sum(trackerInfo['downloadCount'] for trackerInfo in self.trackerInfos.itervalues())
                
            return stats




class PersistentTrackerInfo(TrackerInfo):
    def __init__(self, torrent, btPersister, version):
        self.btPersister = btPersister
        self.version = version
        TrackerInfo.__init__(self, torrent)
    
    
    ##internal functions - persisting
    
    def _updatePersistedData(self, perstData, currentVersion):
        return perstData[:-1]
                
                
    def _loadPersistedData(self):
        perstData = self.btPersister.get('TrackerInfo-trackerInfo', None)
        if perstData is not None:
            perstData = self._updatePersistedData(perstData, self.version)
        return perstData
                    
                    
    def _persist(self):
        trackers = {}
        for trackerId, trackerInfo in self.trackerInfos.iteritems():
            trackers[trackerId] = {'logUrl':trackerInfo['logUrl'],
                                   'tier':trackerInfo['tier']}
        self.btPersister.store('TrackerInfo-trackerInfo', (trackers, self.trackerTiers, self.version))
        
        
    ##internal functions - init
    
    def _initTrackerInfo(self):
        perstData = self._loadPersistedData()
        if perstData is None:
            self._createTrackerInfo()
        else:
            trackers = perstData[0]
            self.trackerTiers = perstData[1]
            self.trackerInfo = {}
            for trackerId, trackerSet in trackers.iteritems():
                self.trackerInfos[trackerId] = self._genTrackerInfo(trackerSet['tier'], trackerId, trackerSet['logUrl'])
            
            
    ##internal functions - tracker - modifying
    
    def _setTrackerInfo(self, newTrackerInfos):
        TrackerInfo._setTrackerInfo(self, newTrackerInfos)
        self._persist()