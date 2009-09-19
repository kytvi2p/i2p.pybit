"""
Copyright 2009  Blub

TorrentList, the class which shows the main dialog, listing all added torrents and their status.
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

from __future__ import with_statement
import logging
import wx

from VirtualListCtrl import PersistentVirtualListCtrl
from Utilities import FunctionCallConverter


class TorrentList(PersistentVirtualListCtrl):
    def __init__(self, persister, version, torrentHandler, childWindow, updateFunc, parent, **kwargs):
        #data Stuff
        self.torrentHandler = torrentHandler
        self.childWindow = childWindow
        
        #logger
        self.log = logging.getLogger('TorrentList')
        
        #columns
        #Syntax: NameOfColumn, NameOfStat, DataType, ColumnWidth
        cols = [('Pos','pos', 'int', 40, True),\
                ('Id','id', 'int', 40, False),\
                ('Status', 'state', 'native', 75, True),\
                ('Name', 'torrentName', 'native', 125, True),\
                ('Size', 'torrentSize', 'dataAmount', 75, True),\
                ('Got', 'progressBytes', 'dataAmount', 75, True),\
                ('Progress', 'progressPercent', 'percent', 75, True),\
                ('Downloaded (R)', 'inRawBytes', 'dataAmount', 115, False),\
                ('Downloaded (P)', 'inPayloadBytes', 'dataAmount', 115, True),\
                ('Downspeed (R)', 'inRawSpeed', 'transferSpeed', 100, True),\
                ('Uploaded (R)', 'outRawBytes', 'dataAmount', 100, False),\
                ('Uploaded (P)', 'outPayloadBytes', 'dataAmount', 100, True),\
                ('Upspeed (R)', 'outRawSpeed', 'transferSpeed', 100, True),\
                ('Peers', ('connectedPeers', 'knownPeers') , 'peerStats', 125, True),\
                ('Avg. Downspeed (R)', 'avgInRawSpeed', 'transferSpeed', 140, False),\
                ('Avg. Downspeed (P)', 'avgInPayloadSpeed', 'transferSpeed', 140, False),\
                ('Avg. Upspeed (R)', 'avgOutRawSpeed', 'transferSpeed', 125, False),\
                ('Avg. Upspeed (P)', 'avgOutPayloadSpeed', 'transferSpeed', 125, False),\
                ('Protocol Overhead', 'protocolOverhead', 'percent', 150, False),\
                ('Superseeding', 'superSeeding', 'bool', 20, False)]
               
        statKw = {'wantedStats':{'bt':'all'},
                  'wantedTorrentStats':{'peers':True,
                                        'queue':True,
                                        'state':True,
                                        'progress':True,
                                        'torrent':True,
                                        'transfer':True,
                                        'transferAverages':True}}
                                        
        func = lambda: updateFunc(**statKw)['bt']
        PersistentVirtualListCtrl.__init__(self, persister, 'TorrentList-', self._updatePerstData, version,
                                           cols, func, parent, rowIdCol='Id', **kwargs)

        #events
        self.Bind(wx.EVT_LIST_ITEM_SELECTED, self.OnSelect)
        self.Bind(wx.EVT_LIST_ITEM_RIGHT_CLICK, self.OnRightClick)
        
        
    def _updatePerstData(self, persColData, currentVersion):
        return persColData
    
        
    def manualUpdate(self):
        with self.lock:
            self.dataUpdate()
        

    def addTorrentByFile(self, torrentFileData, savePath):
        #adds a fresh torrent
        with self.lock:
            #add Task to the handler
            self.torrentHandler.addTorrentByFile(torrentFileData, savePath)
            self.dataUpdate()
            
            
    def addTorrentByUrl(self, torrentUrl, torrentDataPath):
        with self.lock:
            self.torrentHandler.addTorrentByUrl(torrentUrl, torrentDataPath)
            self.dataUpdate()
    

    def OnSelect(self, event):
        with self.lock:
            torrentId = self._getRawData('Id',self.GetFirstSelected())
            self.childWindow(torrentId)
        
        
    def OnStart(self, event):
        #restart a stopped torrent
        with self.lock:
            #for each selected row tell the torrenthandler to restart the torrent
            for row in self._getSelectedRows():
                torrentId = self._getRawData('Id', row)
                self.torrentHandler.startTorrent(torrentId)
            self.dataUpdate()
        

    def OnStop(self, event):
        #stops a running torrent
        with self.lock:
            #stop all selected torrents
            for row in self._getSelectedRows():
                torrentId = self._getRawData('Id', row)
                self.torrentHandler.stopTorrent(torrentId)
            self.dataUpdate()
            

    def OnRemove(self, event):
        #completly removes the torrent from the torrenthandler
        with self.lock:
            #find out which rows were selected
            selectedRows = self._getSelectedRows()
            selectedRows.reverse()

            #remove all selected rows from the list
            for row in selectedRows:
                torrentId = self._getRawData('Id', row)
                self.torrentHandler.removeTorrent(torrentId)

            self.childWindow(None)
            self.dataUpdate()
        

    def OnUp(self, event):
        #moves all selected rows one up in the list
        with self.lock:
            #move all selected rows one up in the list
            for row in self._getSelectedRows():
                torrentId = self._getRawData('Id', row)
                self.torrentHandler.moveTorrent(torrentId, -1)
            self.dataUpdate()
    
    
    def OnMove(self, event):
        #moves all selected rows x steps
        with self.lock:
            selectedRows = self._getSelectedRows()
            if len(selectedRows) > 0:
                lastRow = self._getRowCount()
                downSteps = lastRow - selectedRows[-1] - 1
                upSteps = selectedRows[0] * -1
                diag = wx.NumberEntryDialog(self, 'How many steps should the selected torrents be moved?', 'Steps (up = -, down = +):', 'Move Torrents', 0, upSteps, downSteps)
                if diag.ShowModal() == wx.ID_OK:
                    torrentIds = [self._getRawData('Id', row) for row in selectedRows]
                    steps = diag.GetValue()
                    for torrentId in torrentIds:
                        self.torrentHandler.moveTorrent(torrentId, steps)
            
            self.dataUpdate()
    
    
    def OnDown(self, event):
        #moves all selected rows one up in the list
        with self.lock:
            #move all selected rows one up in the list
            for row in self._getSelectedRows():
                torrentId = self._getRawData('Id', row)
                self.torrentHandler.moveTorrent(torrentId, 1)
            self.dataUpdate()
            
            
    def OnSetSuperSeeding(self, enabled):
        #enables or disables superseeding for all selected torrents
        with self.lock:
            for row in self._getSelectedRows():
                torrentId = self._getRawData('Id', row)
                self.torrentHandler.setSuperSeeding(torrentId, enabled)
                
            self.dataUpdate()
            
        
    def OnRightClick(self, event):
        with self.lock:
            diag = TorrentListOptionsPopup(self)
            self.PopupMenu(diag)




class TorrentListOptionsPopup(wx.Menu):
    def __init__(self,torrentList, *args, **kwargs):
        wx.Menu.__init__(self, *args, **kwargs)
        #static
        self.torrentList = torrentList
        
        #start/stop/remove
        id = wx.NewId()
        self.AppendCheckItem(id, 'Start selected', 'Starts all selected torrents')
        self.Bind(wx.EVT_MENU, self.OnStart, id=id)
        
        id = wx.NewId()
        self.AppendCheckItem(id, 'Stop selected', 'Stops all selected torrents')
        self.Bind(wx.EVT_MENU, self.OnStop, id=id)
        
        id = wx.NewId()
        self.AppendCheckItem(id, 'Remove selected', 'Removes all selected torrents')
        self.Bind(wx.EVT_MENU, self.OnRemove, id=id)
        
        self.AppendSeparator()
        
        #moving
        id = wx.NewId()
        self.AppendCheckItem(id, 'Move selected up', 'Moves all selected torrents one row up')
        self.Bind(wx.EVT_MENU, self.OnMoveUp, id=id)
        
        id = wx.NewId()
        self.AppendCheckItem(id, 'Move selected x rows', 'Moves all selected torrents x rows up or down')
        self.Bind(wx.EVT_MENU, self.OnMoveXRows, id=id)
        
        id = wx.NewId()
        self.AppendCheckItem(id, 'Move selected down', 'Moves all selected torrents one row down')
        self.Bind(wx.EVT_MENU, self.OnMoveDown, id=id)
        
        self.AppendSeparator()
        
        #superseeding menu
        superseedingMenu = wx.Menu()
        superseedingMenu.SetEventHandler(self)
        
        id = wx.NewId()
        superseedingMenu.AppendCheckItem(id, 'Enable', 'Enable superseeding for all selected torrents')
        self.Bind(wx.EVT_MENU, self.OnEnableSuperSeeding, id=id)
        
        id = wx.NewId()
        superseedingMenu.AppendCheckItem(id, 'Disable', 'Disable superseeding for all selected torrents')
        self.Bind(wx.EVT_MENU, self.OnDisableSuperSeeding, id=id)
        
        self.AppendSubMenu(superseedingMenu, 'Superseeding', 'Enable superseeding?')
        
        
    def OnStart(self, event):
        self.torrentList.OnStart(None)
        
        
    def OnStop(self, event):
        self.torrentList.OnStop(None)
        
        
    def OnRemove(self, event):
        self.torrentList.OnRemove(None)
        
        
    def OnMoveUp(self, event):
        self.torrentList.OnUp(None)
        
        
    def OnMoveXRows(self, event):
        self.torrentList.OnMove(None)
        
        
    def OnMoveDown(self, event):
        self.torrentList.OnDown(None)
        
        
    def OnEnableSuperSeeding(self, event):
        self.torrentList.OnSetSuperSeeding(True)
        
        
    def OnDisableSuperSeeding(self, event):
        self.torrentList.OnSetSuperSeeding(False)