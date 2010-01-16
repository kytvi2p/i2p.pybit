"""
Copyright 2009  Blub

TorrentTrackerList, the class which creates the dialog, which shows an overview of the trackers of the selected torrent.
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

import wx

from TrackerModifyDialog import TrackerModifyDialog
from VirtualListCtrl import PersistentVirtualListCtrl

class TorrentTrackerList(PersistentVirtualListCtrl):
    def __init__(self, persister, version, rawUpdateFunc, trackerGetFunc, trackerSetFunc, parent, **kwargs):
        self.persister = persister
        self.version = version
        self.trackerGetFunc = trackerGetFunc
        self.trackerSetFunc = trackerSetFunc
        self.torrentId = None
        
        #Syntax: NameOfColumn, NameOfStat, DataType, ColumnWidth
        cols = [('Id', 'trackerId', 'int', 75, False),\
                ('Tier', 'tier', 'int', 75, False),\
                ('Pos In Tier', 'tierPos', 'int', 75, False),\
                ('Priority', 'trackerPrio', 'int', 75, True),\
                ('Url', 'trackerUrl', 'native', 400, True),\
                ('A', 'active', 'bool', 20, True),\
                ('Seeds', 'seeds', 'int', 75, True),\
                ('Leeches', 'leeches', 'int', 75, True),\
                ('Downloads', 'downloads', 'int', 75, True),\
                ('Last Announce Attempt', 'announceTryTime', 'fullTime', 170, False),\
                ('Last Announce Success', 'announceSuccessTime', 'fullTime', 170, False),\
                ('Last Scrape Attempt', 'scrapeTryTime', 'fullTime', 170, False),\
                ('Last Scrape Success', 'scrapeSuccessTime', 'fullTime', 170, False),\
                ('Announce Attempts', 'announceTryCount', 'int', 170, False),\
                ('Announce Successes', 'announceSuccessCount', 'int', 170, False),\
                ('Scrape Attempts', 'scrapeTryCount', 'int', 170, False),\
                ('Scrape Successes', 'scrapeSuccessCount', 'int', 170, False)]
       
        self.rawUpdateFunc = rawUpdateFunc
        PersistentVirtualListCtrl.__init__(self, persister, 'TorrentTrackerList-', self._updatePerstData, version,
                                           cols, self._getRowData, parent, rowIdCol='Id', defaultSortCol='Priority', defaultSortDirection='DESC', **kwargs)
                                        
        self.Bind(wx.EVT_LIST_ITEM_RIGHT_CLICK, self.OnRightClick, self)
       
        
    def _updatePerstData(self, persColData, currentVersion):
        return persColData
    
        
    def _getRowData(self):
        if self.torrentId is None:
            data = []
        else:
            statKw = {'wantedStats':{'bt':self.torrentId},
                      'wantedTorrentStats':{'tracker':True}}
            data = self.rawUpdateFunc(**statKw)['bt']['tracker']
        return data
    
        
    def _popTrackerSet(self, trackerId, trackerInfos):
        tracker = None
        tierIdx = 0
        while tierIdx < len(trackerInfos):
            #check tier
            tier = trackerInfos[tierIdx]
            trackerIdx = 0
            while trackerIdx < len(tier):
                #check each tracker
                if not tier[trackerIdx]['trackerId'] == trackerId:
                    #wrong one
                    trackerIdx += 1
                else:
                    #found the right one
                    tracker = tier[trackerIdx]
                    del tier[trackerIdx]
                    if len(tier) == 0:
                        del trackerInfos[tierIdx]
                    
                    #terminate
                    trackerIdx = len(tier)
                    tierIdx = len(trackerInfos)
            
            tierIdx += 1
                
        return tracker
        

    def changeTorrentId(self, torrentId):
        self.lock.acquire()
        if self.torrentId is not None and torrentId is None:
            #got disabled
            self.torrentId = None
            self.clear()
            
        elif self.torrentId is None and torrentId is not None:
            #got enabled
            self.torrentId = torrentId
            self.dataUpdate()
            
        elif self.torrentId is not None and torrentId is not None:
            #normal change
            if not self.torrentId == torrentId:
                self.torrentId = torrentId
                self.dataUpdate()
        self.lock.release()
        

    def manualUpdate(self):
        self.lock.acquire()
        if self.torrentId is not None:
            self.dataUpdate()
        self.lock.release()
        
    ##tracker actions
    
    def getTrackerInfo(self):
        self.lock.acquire()
        trackerInfo = self.trackerGetFunc(self.torrentId)
        self.lock.release()
        return trackerInfo
    
    
    def setTrackerInfo(self, newTrackerInfo):
        self.lock.acquire()
        self.trackerSetFunc(self.torrentId, newTrackerInfo)
        self.dataUpdate()
        self.lock.release()
        
        
    def makeTrackerPreffered(self):
        self.lock.acquire()
        selectedRows = self._getSelectedRows()
        trackerIds = [self._getRawData('Id', row) for row in selectedRows]
        if len(trackerIds) > 0:
            trackerInfos = self.trackerGetFunc(self.torrentId)
            tracker = [self._popTrackerSet(trackerId, trackerInfos) for trackerId in trackerIds]
            if len(tracker) > 0:
                trackerInfos.insert(0, tracker)
                self.trackerSetFunc(self.torrentId, trackerInfos)
                self.dataUpdate()
        self.lock.release()
        
    
    def makeTrackerBackup(self):
        self.lock.acquire()
        selectedRows = self._getSelectedRows()
        trackerIds = [self._getRawData('Id', row) for row in selectedRows]
        if len(trackerIds) > 0:
            trackerInfos = self.trackerGetFunc(self.torrentId)
            tracker = [self._popTrackerSet(trackerId, trackerInfos) for trackerId in trackerIds]
            if len(tracker) > 0:
                trackerInfos.append(tracker)
                self.trackerSetFunc(self.torrentId, trackerInfos)
                self.dataUpdate()
        self.lock.release()
        
    
    ##events
        
    def OnRightClick(self, event):
        diag = TrackerOptionsPopup(self, self.persister, self.version)
        self.PopupMenu(diag)
        
        


class TrackerOptionsPopup(wx.Menu):
    def __init__(self, trackerDiag, persister, version, *args, **kwargs):
        wx.Menu.__init__(self, *args, **kwargs)
        #static
        self.trackerDiag = trackerDiag
        self.persister = persister
        self.version = version
        
        #menu
        id = wx.NewId()
        self.AppendCheckItem(id, 'Reset to defaults ', 'Restore the default tracker list as stored in the torrent')
        self.Bind(wx.EVT_MENU, self.OnResetToDefaults, id=id)
        
        self.AppendSeparator()
        
        id = wx.NewId()
        self.AppendCheckItem(id, 'Make preffered', 'Make this tracker the preffered one')
        self.Bind(wx.EVT_MENU, self.OnMakePreffered, id=id)
        
        id = wx.NewId()
        self.AppendCheckItem(id, 'Make backup', 'Make this tracker the least preffered one')
        self.Bind(wx.EVT_MENU, self.OnMakeBackup, id=id)
        
        self.AppendSeparator()
        
        id = wx.NewId()
        self.AppendCheckItem(id, 'Modify tracker list', 'Modify tracker list')
        self.Bind(wx.EVT_MENU, self.OnModify, id=id)
    
        
    def OnResetToDefaults(self, event):
        self.trackerDiag.setTrackerInfo(None)
        
        
    def OnMakePreffered(self, event):
        self.trackerDiag.makeTrackerPreffered()
        
        
    def OnMakeBackup(self, event):
        self.trackerDiag.makeTrackerBackup()
        

    def OnModify(self, event):
        TrackerModifyDialog(self.trackerDiag, self.trackerDiag.getTrackerInfo(), self.trackerDiag.setTrackerInfo, self.persister, self.version)
