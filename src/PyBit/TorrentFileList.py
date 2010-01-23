"""
Copyright 2009  Blub

TorrentConnectionList, the class which creates the dialog, which shows the files of the selected torrent.
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

from VirtualListCtrl import PersistentVirtualListCtrl

class TorrentFileList(PersistentVirtualListCtrl):
    def __init__(self, persister, version, rawUpdateFunc, setPrioFunc, setWantedFlagFunc, parent, **kwargs):
        self.setPrioFunc = setPrioFunc
        self.setWantedFlagFunc = setWantedFlagFunc
        self.torrentId = None
  
        #Syntax: NameOfColumn, NameOfStat, DataType, ColumnWidth
        cols = [('Id', 'id', 'int', 50, False),
                ('Path', 'path', 'native', 500, True),
                ('Size', 'size', 'dataAmount', 75, True),
                ('Progress', 'progress', 'percent', 75, True),
                ('D', 'wanted', 'bool', 20, True),
                ('Priority', 'priority', 'int', 75, True),
                ('First Piece', 'firstPiece', 'int', 75, False),
                ('Last Piece', 'lastPiece', 'int', 75, False),
                ('Min. Availability', 'minAvailability', 'int', 75, False),
                ('Avg. Availability', 'avgAvailability', 'float', 75, False)]
       
        self.rawUpdateFunc = rawUpdateFunc
        PersistentVirtualListCtrl.__init__(self, persister, 'TorrentFileList-', self._updatePerstData, version,
                                           cols, self._getRowData, parent, rowIdCol='Id', **kwargs)
        
        self.Bind(wx.EVT_LIST_ITEM_RIGHT_CLICK, self.OnRightClick)
        
        
    def _updatePerstData(self, persColData, currentVersion):
        return persColData
        
        
    def _getRowData(self):
        if self.torrentId is None:
            data = []
        else:
            statKw = {'wantedStats':{'bt':self.torrentId},
                      'wantedTorrentStats':{'files':True}}
            data = self.rawUpdateFunc(**statKw)['bt']['files']
        return data
        

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
        
        
    ##general funcs
        
    def setPriority(self):
        selectedRows = self._getSelectedRows()
        diag = wx.NumberEntryDialog(self, 'Enter the new priority for the selected files.', 'Priority:', 'Set Priority', 0, -262144, 262144)
        if diag.ShowModal() == wx.ID_OK:
            fileIds = [self._getRawData('Id', row) for row in selectedRows]
            if len(fileIds) > 0:
                self.setPrioFunc(self.torrentId, fileIds, diag.GetValue())
                
                
    def setIncrementalPriority(self, direction):
        selectedRows = self._getSelectedRows()
        diag = wx.NumberEntryDialog(self, 'Enter the lowest priority value which should be assigned.', 'Priority:', 'Lowest Priority', 0, -262144, 262144)
        if diag.ShowModal() == wx.ID_OK:
            fileIds = [self._getRawData('Id', row) for row in selectedRows]
            if len(fileIds) > 0:
                prio = diag.GetValue()
                if direction == 'Desc':
                    fileIds.reverse()
                for fileId in fileIds:
                    self.setPrioFunc(self.torrentId, (fileId,), prio)
                    prio += 1
                
                
    def setWantedFlag(self, wanted):
        selectedRows = self._getSelectedRows()
        fileIds = [self._getRawData('Id', row) for row in selectedRows]
        if len(fileIds) > 0:
            self.setWantedFlagFunc(self.torrentId, fileIds, wanted)
            
    ##events
        
    def OnRightClick(self, event):
        diag = FileOptionsPopup(self)
        self.PopupMenu(diag)
        
        
        
        
class FileOptionsPopup(wx.Menu):
    def __init__(self, fileDiag, *args, **kwargs):
        wx.Menu.__init__(self, *args, **kwargs)
        #static
        self.fileDiag = fileDiag
        
        #wanted menu
        wantedMenu = wx.Menu()
        wantedMenu.SetEventHandler(self)
        
        id = wx.NewId()
        wantedMenu.AppendCheckItem(id, 'Yes', 'Download this file')
        self.Bind(wx.EVT_MENU, self.OnWantedFile, id=id)
        
        id = wx.NewId()
        wantedMenu.AppendCheckItem(id, 'No', 'Don\'t download this file')
        self.Bind(wx.EVT_MENU, self.OnUnwantedFile, id=id)
        
        self.AppendSubMenu(wantedMenu, 'Download File(s)', 'Download the selected files?')
        
        #prio menu
        prioMenu = wx.Menu()
        prioMenu.SetEventHandler(self)
        
        id = wx.NewId()
        prioMenu.Append(id, 'Normal', 'Set entered Priority for all selected files')
        self.Bind(wx.EVT_MENU, self.OnSetNormalPrio, id=id)
        
        id = wx.NewId()
        prioMenu.Append(id, 'Incremental (Asc)', 'Assigns increasing priority values, starting from the entered priority')
        self.Bind(wx.EVT_MENU, self.OnSetAscIncrementalPrio, id=id)
        
        id = wx.NewId()
        prioMenu.Append(id, 'Incremental (Desc)', 'Assigns increasing priority values, starting from the entered priority')
        self.Bind(wx.EVT_MENU, self.OnSetDescIncrementalPrio, id=id)
        
        self.AppendSubMenu(prioMenu, 'Set Priority', 'Sets the priority of the selected files')
        

    def OnSetAscIncrementalPrio(self, event):
        self.fileDiag.setIncrementalPriority('Asc')
        
        
    def OnSetDescIncrementalPrio(self, event):
        self.fileDiag.setIncrementalPriority('Desc')
        
        
    def OnSetNormalPrio(self, event):
        self.fileDiag.setPriority()
        
        
    def OnWantedFile(self, event):
        self.fileDiag.setWantedFlag(True)
        
    
    def OnUnwantedFile(self, event):
        self.fileDiag.setWantedFlag(False)