"""
Copyright 2009  Blub

TrackerModifyDialog, a panel and frame for modifying tracker structures (supporting tracker groups).
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

from Bittorrent.HttpUtilities import joinUrl, splitUrl, i2pHttpUrlRegexObj
from Utilities import showInfoMessage, showWarningMessage, showErrorMessage
from VirtualListCtrl import PersistentVirtualListCtrl


class TrackerModifyPanel(wx.Panel):
    def __init__(self, parent, trackerInfo, persister, version, **kwargs):
        wx.Panel.__init__(self, parent, **kwargs)
        
        ##VARS
        self.trackerInfo = [{'groupId':tierIdx, 'groupPos':tierIdx+1, 'groupName':'Group '+str(tierIdx), 'groupTracker':tier} for tierIdx, tier in enumerate(trackerInfo)]
        if len(self.trackerInfo) == 0:
            self.selectedGroup = None
            self.nextGroupId = 0
            self.nextTrackerId = 0
        else:
            self.selectedGroup = 0
            self.nextGroupId = max(tier['groupId'] for tier in self.trackerInfo) + 1
            self.nextTrackerId = max(max(tracker['trackerId'] for tracker in tier['groupTracker']) for tier in self.trackerInfo) + 1
            
        
        self.knownTrackerMapper = {u'crstrack.i2p':u'http://mm3zx3besctrx6peq5wzzueil237jdgscuvn5ugwilxrwzyuajja.b32.i2p/tracker/announce.php',
                                   u'tracker2.postman.i2p':u'http://lnQ6yoBTxQuQU8EQ1FlF395ITIQF-HGJxUeFvzETLFnoczNjQvKDbtSB7aHhn853zjVXrJBgwlB9sO57KakBDaJ50lUZgVPhjlI19TgJ-CxyHhHSCeKx5JzURdEW-ucdONMynr-b2zwhsx8VQCJwCEkARvt21YkOyQDaB9IdV8aTAmP~PUJQxRwceaTMn96FcVenwdXqleE16fI8CVFOV18jbJKrhTOYpTtcZKV4l1wNYBDwKgwPx5c0kcrRzFyw5~bjuAKO~GJ5dR7BQsL7AwBoQUS4k1lwoYrG1kOIBeDD3XF8BWb6K3GOOoyjc1umYKpur3G~FxBuqtHAsDRICkEbKUqJ9mPYQlTSujhNxiRIW-oLwMtvayCFci99oX8MvazPS7~97x0Gsm-onEK1Td9nBdmq30OqDxpRtXBimbzkLbR1IKObbg9HvrKs3L-kSyGwTUmHG9rSQSoZEvFMA-S0EXO~o4g21q1oikmxPMhkeVwQ22VHB0-LZJfmLr4SAAAA.i2p/announce.php',
                                   u'tracker.thepiratebay.i2p':u'http://tracker.thepiratebay.i2p/announce',
                                   u'tracker.welterde.i2p':u'http://tracker.welterde.i2p/announce'}
                                
        ##GUI
        panelItems = wx.GridBagSizer(vgap = 0, hgap = 0)
        
        #splitter
        self.splitter = wx.SplitterWindow(self, style=wx.CLIP_CHILDREN)
        self.splitter.SetMinimumPaneSize(200)
        
        
        ##tracker groups
        
        groupPanel = wx.Panel(self.splitter)
        groupPanelSizer = wx.GridBagSizer(vgap = 0, hgap = 6)
        
        #group list
        #Syntax: NameOfColumn, NameOfStat, DataType, ColumnWidth
        cols = [('Id', 'groupId', 'int', 75, False),\
                ('Pos', 'groupPos', 'int', 40, True),\
                ('Group', 'groupName', 'native', 100, True)]
                
        listboxId = wx.NewId()
        self.trackerGroupList = PersistentVirtualListCtrl(persister, 'TorrentModifyDialog-TrackerGroupList-', self._updateGroupPerstData, version,
                                                          cols, self._getTrackerGroupData, rowIdCol='Id', allowSort=False, defaultSortCol='Pos',
                                                          parent=groupPanel, id=listboxId, size=wx.Size(140, -1))
        self.trackerGroupList.SetToolTipString('')
        groupPanelSizer.Add(self.trackerGroupList, (0,1), (6,1), wx.EXPAND | wx.ALL, border = 0)
        
        
        #buttons
        buttonAdd = wx.Button(groupPanel, wx.ID_ADD, "")
        groupPanelSizer.Add(buttonAdd, (1,0), (1,1), wx.EXPAND | wx.TOP | wx.BOTTOM, border=7)
        wx.EVT_BUTTON(buttonAdd, wx.ID_ADD, self.OnGroupAdd)
        
        buttonMoveUp = wx.Button(groupPanel, wx.ID_UP, "")
        groupPanelSizer.Add(buttonMoveUp, (2,0), (1,1), wx.EXPAND | wx.TOP | wx.BOTTOM, border=7)
        wx.EVT_BUTTON(buttonMoveUp, wx.ID_UP, self.OnGroupMoveUp)
        
        buttonId = wx.NewId()
        buttonMoveDown = wx.Button(groupPanel, wx.ID_DOWN, "")
        groupPanelSizer.Add(buttonMoveDown, (3,0), (1,1), wx.EXPAND | wx.TOP | wx.BOTTOM, border=7)
        wx.EVT_BUTTON(buttonMoveDown, wx.ID_DOWN, self.OnGroupMoveDown)
        
        buttonId = wx.NewId()
        buttonRemove = wx.Button(groupPanel, wx.ID_DELETE, "")
        groupPanelSizer.Add(buttonRemove, (4,0), (1,1), wx.EXPAND | wx.TOP | wx.BOTTOM, border=7)
        wx.EVT_BUTTON(buttonRemove, wx.ID_DELETE, self.OnGroupRemove)

        
        #sizer
        groupPanelSizer.AddGrowableCol(1, 1)
        groupPanelSizer.AddGrowableRow(0, 1)
        groupPanelSizer.AddGrowableRow(5, 1)
        groupPanel.SetSizer(groupPanelSizer)
        
        
        ##tracker urls
        
        urlPanel = wx.Panel(self.splitter)
        urlPanelSizer = wx.GridBagSizer(vgap = 0, hgap = 6)
        
        #url list
        #Syntax: NameOfColumn, NameOfStat, DataType, ColumnWidth
        cols = [('Id', 'trackerId', 'int', 75, False),\
                ('Position', 'tierPos', 'int', 75, True),\
                ('Url', 'trackerUrl', 'native', 385, True),\
                ('A', 'active', 'bool', 20, False),\
                ('Seeds', 'seeds', 'int', 75, False),\
                ('Leeches', 'leeches', 'int', 75, False),\
                ('Downloads', 'downloads', 'int', 75, False),\
                ('Last Announce Attempt', 'announceTryTime', 'fullTime', 170, False),\
                ('Last Announce Success', 'announceSuccessTime', 'fullTime', 170, False),\
                ('Last Scrape Attempt', 'scrapeTryTime', 'fullTime', 170, False),\
                ('Last Scrape Success', 'scrapeSuccessTime', 'fullTime', 170, False),\
                ('Announce Attempts', 'announceTryCount', 'int', 170, False),\
                ('Announce Successes', 'announceSuccessCount', 'int', 170, False),\
                ('Scrape Attempts', 'scrapeTryCount', 'int', 170, False),\
                ('Scrape Successes', 'scrapeSuccessCount', 'int', 170, False)]
        
        listboxId = wx.NewId()
        self.trackerUrlList = PersistentVirtualListCtrl(persister, 'TorrentModifyDialog-TrackerUrlList-', self._updateTrackerPerstData, version,
                                                        cols, self._getTrackerUrlData, rowIdCol='Id', allowSort=False, defaultSortCol='Position',
                                                        parent=urlPanel, id=listboxId)
        self.trackerUrlList.SetToolTipString('')
        urlPanelSizer.Add(self.trackerUrlList, (0,0), (7,2), wx.EXPAND)
        wx.EVT_LIST_ITEM_RIGHT_CLICK(self.trackerUrlList, listboxId, self.OnTrackerListRightClick)
        
        #combo + url box
        boxId = wx.NewId()
        self.trackerName = wx.ComboBox(urlPanel, boxId, size = wx.Size(155, -1),\
                                       choices=sorted(self.knownTrackerMapper.iterkeys()) + ['other'], style=wx.CB_READONLY)
        self.trackerName.SetToolTipString('Either select one of the predefined trackers here or select "other" to enter a different tracker announce url in the text box to the right')
        urlPanelSizer.Add(self.trackerName, (7,0), (1,1), wx.TOP, border = 4)
        wx.EVT_COMBOBOX(self, boxId, self.OnTrackerNameSelect)
                                    
        self.trackerAnnounceUrl = wx.TextCtrl(urlPanel, -1, "") 
        self.trackerAnnounceUrl.SetToolTipString('The full announce url of the tracker, including the "http://"-prefix.')
        self.trackerAnnounceUrl.Disable()
        urlPanelSizer.Add(self.trackerAnnounceUrl, (7,1), (1,1), wx.EXPAND | wx.FIXED_MINSIZE | wx.TOP, border = 4)
        
        
        #buttons
        buttonAdd = wx.Button(urlPanel, wx.ID_ADD, "")
        urlPanelSizer.Add(buttonAdd, (2,2), (1,1), wx.EXPAND | wx.TOP | wx.BOTTOM, border=7)
        wx.EVT_BUTTON(buttonAdd, wx.ID_ADD, self.OnTrackerAdd)
        
        buttonMoveUp = wx.Button(urlPanel, wx.ID_UP, "")
        urlPanelSizer.Add(buttonMoveUp, (3,2), (1,1), wx.EXPAND | wx.TOP | wx.BOTTOM, border=7)
        wx.EVT_BUTTON(buttonMoveUp, wx.ID_UP, self.OnTrackerMoveUp)
        
        buttonMoveDown = wx.Button(urlPanel, wx.ID_DOWN, "")
        urlPanelSizer.Add(buttonMoveDown, (4,2), (1,1), wx.EXPAND | wx.TOP | wx.BOTTOM, border=7)
        wx.EVT_BUTTON(buttonMoveDown, wx.ID_DOWN, self.OnTrackerMoveDown)
        
        buttonId = wx.NewId()
        buttonRemove = wx.Button(urlPanel, wx.ID_DELETE, "")
        urlPanelSizer.Add(buttonRemove, (5,2), (1,1), wx.EXPAND | wx.TOP | wx.BOTTOM, border=7)
        wx.EVT_BUTTON(buttonRemove, wx.ID_DELETE, self.OnTrackerRemove)
        
        
        #sizer
        urlPanelSizer.AddGrowableCol(1, 1)
        urlPanelSizer.AddGrowableRow(1, 1)
        urlPanelSizer.AddGrowableRow(6, 1)
        urlPanel.SetSizer(urlPanelSizer)
        
        
        ##main sizer
        self.splitter.SplitVertically(groupPanel, urlPanel, 228)
        panelItems.Add(self.splitter, (0,0), (1,1), wx.EXPAND | wx.ALL, border = 2)
        panelItems.AddGrowableCol(0, 1)
        panelItems.AddGrowableRow(0, 1)
        self.SetSizer(panelItems)
        
        
        #fill lists
        self.trackerGroupList.dataUpdate()
        if len(self.trackerInfo) > 0:
            self.trackerGroupList.Select(0, on=1)
        self.trackerUrlList.dataUpdate()
        
        
        ##EVENTS
        self.Bind(wx.EVT_LIST_ITEM_SELECTED, self.OnSelect, self.trackerGroupList)
        
        
    ##internal functions - list persisting
    
    def _updateGroupPerstData(self, persColData, currentVersion):
        return persColData
    
    
    def _updateTrackerPerstData(self, persColData, currentVersion):
        return persColData
        
        
    ##internal functions - refresh
    
    def _getTrackerGroupData(self):
        for i in xrange(0, len(self.trackerInfo)):
            self.trackerInfo[i]['groupPos'] = i+1
        return self.trackerInfo
    
    
    def _getTrackerUrlData(self):
        if self.selectedGroup is None:
            data = []
        else:
            data = self.trackerInfo[self.selectedGroup]['groupTracker']
            for i in xrange(0, len(data)):
                data[i]['tierPos'] = i+1
        return data
    
    
    ##external functions - tracker info
    
    def getTrackerInfo(self):
        return [tier['groupTracker'] for tier in self.trackerInfo]
    
    
    ##external functions - events - other
    
    def OnSelect(self, event):
        newGroup = self.trackerGroupList.getRawData('Pos',self.trackerGroupList.GetFirstSelected()) - 1
        if not self.selectedGroup == newGroup:
            self.selectedGroup = newGroup
            self.trackerUrlList.dataUpdate()
            
    
    def OnTrackerNameSelect(self, event):
        selectedTracker = self.trackerName.GetValue()
        if not selectedTracker == '':
            #something did get selected
            if selectedTracker in self.knownTrackerMapper:
                self.trackerAnnounceUrl.Disable()
                self.trackerAnnounceUrl.SetValue(self.knownTrackerMapper[selectedTracker])
            
            elif selectedTracker == u'other':
                if not self.trackerAnnounceUrl.IsEnabled():
                    #currently disabled
                    self.trackerAnnounceUrl.SetValue('http://')
                    self.trackerAnnounceUrl.Enable()
            
    
    ## external functions - events - groups
    
    def OnGroupAdd(self, event):
        #determine position for insert
        groupIdx = self.selectedGroup
        if groupIdx is None:
            groupIdx = 0
        else:
            groupIdx += 1
        
        #insert new group
        self.trackerInfo.insert(groupIdx, {'groupId':self.nextGroupId, 'groupPos':groupIdx+1,
                                           'groupName':'Group '+str(self.nextGroupId), 'groupTracker':[]})
        self.nextGroupId += 1
        
        #update list
        self.trackerGroupList.dataUpdate()
        
        #check if it should be selected
        if self.selectedGroup is None:
            self.selectedGroup = groupIdx
            self.trackerGroupList.Select(groupIdx, on=1)
    
    
    def OnGroupRemove(self, event):
        #remove all selected groups
        selectedGroups = self.trackerGroupList.getSelectedRows()
        selectedGroups.reverse()
        for groupIdx in selectedGroups:
            del self.trackerInfo[groupIdx]
            if groupIdx == self.selectedGroup:
                self.selectedGroup = None
        self.trackerGroupList.dataUpdate()
        self.trackerUrlList.dataUpdate()
    
    
    def OnGroupMoveUp(self, event):
        #move all selected groups one row up
        selectedGroups = self.trackerGroupList.getSelectedRows()
        for groupIdx in selectedGroups:
            if groupIdx > 0:
                self.trackerInfo.insert(groupIdx-1, self.trackerInfo.pop(groupIdx))
        self.trackerGroupList.dataUpdate()
                
    
    def OnGroupMoveDown(self, event):
        #move all selected groups one row down
        selectedGroups = self.trackerGroupList.getSelectedRows()
        selectedGroups.reverse()
        for groupIdx in selectedGroups:
            if groupIdx < len(self.trackerInfo) - 1:
                self.trackerInfo.insert(groupIdx+1, self.trackerInfo.pop(groupIdx))
        self.trackerGroupList.dataUpdate()
    
    
    ##external funcs - events - tracker
    
    def OnTrackerAdd(self, event):
        if self.selectedGroup is None:
            #no group selected
            showErrorMessage(self, 'You need to select a tracker group, before you can add a tracker!')
        else:
            #group selected, go on
            tier = self.trackerInfo[self.selectedGroup]['groupTracker']
            trackerUrl = self.trackerAnnounceUrl.GetValue()
            if i2pHttpUrlRegexObj.match(trackerUrl) is None:
                #invalid url
                showErrorMessage(self, 'The url "%s" is not a valid i2p http url!', trackerUrl)
            else:
                #valid
                trackerPos = self.trackerUrlList.GetFirstSelected()
                if trackerPos == -1:
                    trackerPos = 0
                else:
                    trackerPos += 1
                    
                tier.insert(trackerPos, {'tier':self.selectedGroup + 1,
                                         'tierPos':trackerPos + 1,
                                         'trackerUrl':trackerUrl,
                                         'trackerId':self.nextTrackerId,
                                         'active':False,
                                         'announceTryCount':None,
                                         'announceTryTime':None,
                                         'announceSuccessCount':None,
                                         'announceSuccessTime':None,
                                         'scrapeTryCount':None,
                                         'scrapeTryTime':None,
                                         'scrapeSuccessCount':None,
                                         'scrapeSuccessTime':None,
                                         'seeds':None,
                                         'leeches':None,
                                         'downloads':None})
                self.nextTrackerId += 1
                
                self.trackerUrlList.dataUpdate()
    
    
    def OnTrackerRemove(self, event):
        if self.selectedGroup is not None:
            tier = self.trackerInfo[self.selectedGroup]['groupTracker']
            selectedTrackers = self.trackerUrlList.getSelectedRows()
            selectedTrackers.reverse()
            for trackerIdx in selectedTrackers:
                del tier[trackerIdx]
            self.trackerUrlList.dataUpdate()
    
    
    def OnTrackerMoveUp(self, event):
        if self.selectedGroup is not None:
            tier = self.trackerInfo[self.selectedGroup]['groupTracker']
            selectedTrackers = self.trackerUrlList.getSelectedRows()
            for trackerIdx in selectedTrackers:
                if trackerIdx > 0:
                    tier.insert(trackerIdx-1, tier.pop(trackerIdx))
            self.trackerUrlList.dataUpdate()
    
    
    def OnTrackerMoveDown(self, event):
        if self.selectedGroup is not None:
            tier = self.trackerInfo[self.selectedGroup]['groupTracker']
            selectedTrackers = self.trackerUrlList.getSelectedRows()
            selectedTrackers.reverse()
            for trackerIdx in selectedTrackers:
                if trackerIdx < len(tier) - 1:
                    tier.insert(trackerIdx+1, tier.pop(trackerIdx))
            self.trackerUrlList.dataUpdate()
            
            
    def OnTrackerChangeUrl(self):
        trackerIdx = self.trackerUrlList.GetFirstSelected()
        if trackerIdx == -1:
            #no tracker selected
            showErrorMessage(self, 'You need to select a tracker, before you can change its url!')
        else:
            #a tracker was selected
            tracker = self.trackerInfo[self.selectedGroup]['groupTracker'][trackerIdx]
            diag = wx.TextEntryDialog(self, message='Please enter the new url for this tracker:', caption='Enter url', defaultValue=tracker['trackerUrl'])
        
            if diag.ShowModal() == wx.ID_OK:
                #user did hit ok
                trackerUrl = diag.GetValue()
                if i2pHttpUrlRegexObj.match(trackerUrl) is None:
                    #invalid url
                    showErrorMessage(self, 'The url "%s" is not a valid i2p http url!', trackerUrl)
                else:
                    #valid
                    tracker['trackerUrl'] = trackerUrl
                    self.trackerUrlList.dataUpdate()
                    
                    
    def OnTrackerMoveToGroup(self):
        trackerIdx = self.trackerUrlList.GetFirstSelected()
        if trackerIdx == -1:
            #no tracker selected
            showErrorMessage(self, 'You need to select a tracker, before you can move it to a different group!')
        else:
            #a tracker was selected
            diag = wx.SingleChoiceDialog(self, message='Please select the new group for this tracker:', caption='Select group', choices=[tier['groupName'] for tier in self.trackerInfo]) 
            if diag.ShowModal() == wx.ID_OK:
                #user did hit ok
                newGroupIdx = diag.GetSelection()
                if not newGroupIdx == self.selectedGroup:
                    #not the current one
                    tracker = self.trackerInfo[self.selectedGroup]['groupTracker'][trackerIdx]
                    del self.trackerInfo[self.selectedGroup]['groupTracker'][trackerIdx]
                    self.trackerInfo[newGroupIdx]['groupTracker'].append(tracker)
                    
                    #move selection
                    self.trackerGroupList.Select(self.selectedGroup, on=0)
                    self.trackerGroupList.Select(newGroupIdx, on=1)
                    
                
    
    def OnTrackerListRightClick(self, event):
        diag = TrackerListOptionsPopup(self)
        self.PopupMenu(diag)
        
        


class TrackerListOptionsPopup(wx.Menu):
    def __init__(self, trackerModifyPanel, *args, **kwargs):
        wx.Menu.__init__(self, *args, **kwargs)
        #static
        self.trackerModifyPanel = trackerModifyPanel
        
        #menu
        id = wx.NewId()
        self.AppendCheckItem(id, 'Change url', 'Change the url of the selected tracker')
        self.Bind(wx.EVT_MENU, self.OnChangeUrl, id=id)
        
        id = wx.NewId()
        self.AppendCheckItem(id, 'Move to other group', 'Move the selected tracker to another group')
        self.Bind(wx.EVT_MENU, self.OnMoveToGroup, id=id)
    
        
    def OnChangeUrl(self, event):
        self.trackerModifyPanel.OnTrackerChangeUrl()
        
        
    def OnMoveToGroup(self, event):
        self.trackerModifyPanel.OnTrackerMoveToGroup()





class TrackerModifyDialog(wx.Frame):
    def __init__(self, parent, trackerInfo, trackerSetFunc, persister, version, **kwargs):
        wx.Frame.__init__(self, parent, -1, 'Modify Trackers', size=wx.Size(800, 400),\
                          style = wx.DEFAULT_FRAME_STYLE, **kwargs)
        
        ##vars
        self.trackerSetFunc = trackerSetFunc
        
        
        ##basics
        self.CentreOnScreen()
        frameSizer = wx.BoxSizer(wx.VERTICAL)
        
        mainPanel = wx.Panel(self)
        mainPanelSizer = wx.BoxSizer(wx.VERTICAL)
        mainPanelItems = wx.GridBagSizer(vgap = 0, hgap = 6)
        
        ##tracker panel
        self.trackerPanel = TrackerModifyPanel(mainPanel, trackerInfo, persister, version)
        mainPanelItems.Add(self.trackerPanel, (0,0), (1,1), wx.EXPAND | wx.ALL, border = 2)
        
        
        ##buttons
        
        mainPanelButtonItems = wx.GridBagSizer(vgap = 3, hgap = 5)
        
        #create button
        button = wx.Button(mainPanel, wx.ID_OK, "")
        mainPanelButtonItems.Add(button, (0,0), (1,1), wx.ALIGN_CENTER_HORIZONTAL)
        wx.EVT_BUTTON(button, wx.ID_OK, self.OnOkButton)
        
        #cancel button
        button = wx.Button(mainPanel, wx.ID_CANCEL, "", style=wx.BU_EXACTFIT)
        mainPanelButtonItems.Add(button, (0,1), (1,1), wx.ALIGN_CENTER_HORIZONTAL)
        wx.EVT_BUTTON(button, wx.ID_CANCEL, self.OnCancelButton)
        self.Bind(wx.EVT_CLOSE, self.OnCancelButton)
        
        #sizer
        mainPanelButtonItems.AddGrowableCol(0, 1)
        mainPanelButtonItems.AddGrowableCol(1, 1)
        mainPanelItems.Add(mainPanelButtonItems, (1,0), (1,1), wx.EXPAND | wx.ALL, border = 2)
        
        
        ##main
        mainPanelItems.AddGrowableCol(0, 1)
        mainPanelItems.AddGrowableRow(0, 1)
        mainPanelSizer.Add(mainPanelItems, 1, wx.EXPAND | wx.ALL, border = 2)
        mainPanel.SetSizer(mainPanelSizer)
        
        frameSizer.Add(mainPanel, 1, wx.EXPAND | wx.ALL, border = 0)
        self.SetSizer(frameSizer)
        self.Layout()
        self.Show()
        
        
    def OnOkButton(self, event):
        self.trackerSetFunc(self.trackerPanel.getTrackerInfo())
        self.Destroy()
    
    
    def OnCancelButton(self, event):
        self.Destroy()
        
        
if __name__ == '__main__':
    #create GUI
    app = wx.App()
    merk = TrackerModifyDialog(None, [])
    app.MainLoop()