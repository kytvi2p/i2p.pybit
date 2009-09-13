"""
Copyright 2009  Blub

TorrentCreateDialog, a class which creates a dialog which allows the creation of new torrents.
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


from time import time
import math
import os
import wx

from Bittorrent.TorrentCreator import TorrentCreator, TorrentCreatorException
from Conversion import dataAmountToString
from Utilities import normalisePath, scaleInt, showInfoMessage, showWarningMessage, showErrorMessage

class TorrentCreateDialog(wx.Frame):
    def __init__(self, progPath, parent, **kwargs):
        wx.Frame.__init__(self, parent, -1, 'Create Torrent', size=wx.Size(700, 550),\
                          style = wx.DEFAULT_FRAME_STYLE, **kwargs)
        
        ##non-GUI
        self.progPath = progPath
        self.torrentCreator = TorrentCreator()
        
        timerId = wx.NewId()
        self.updateTimer = wx.Timer(self, timerId)
        wx.EVT_TIMER(self, timerId, self.OnTimer)

        ##mapper
        self.knownTrackerMapper = {u'crstrack.i2p':u'http://mm3zx3besctrx6peq5wzzueil237jdgscuvn5ugwilxrwzyuajja.b32.i2p/tracker/announce.php',
                                   u'tracker.postman.i2p':u'http://YRgrgTLGnbTq2aZOZDJQ~o6Uk5k6TK-OZtx0St9pb0G-5EGYURZioxqYG8AQt~LgyyI~NCj6aYWpPO-150RcEvsfgXLR~CxkkZcVpgt6pns8SRc3Bi-QSAkXpJtloapRGcQfzTtwllokbdC-aMGpeDOjYLd8b5V9Im8wdCHYy7LRFxhEtGb~RL55DA8aYOgEXcTpr6RPPywbV~Qf3q5UK55el6Kex-6VCxreUnPEe4hmTAbqZNR7Fm0hpCiHKGoToRcygafpFqDw5frLXToYiqs9d4liyVB-BcOb0ihORbo0nS3CLmAwZGvdAP8BZ7cIYE3Z9IU9D1G8JCMxWarfKX1pix~6pIA-sp1gKlL1HhYhPMxwyxvuSqx34o3BqU7vdTYwWiLpGM~zU1~j9rHL7x60pVuYaXcFQDR4-QVy26b6Pt6BlAZoFmHhPcAuWfu-SFhjyZYsqzmEmHeYdAwa~HojSbofg0TMUgESRXMw6YThK1KXWeeJVeztGTz25sL8AAAA.i2p/announce.php',
                                   u'tracker.welterde.i2p':u'http://tracker.welterde.i2p/announce'}
                        
        self.pieceSizeMapper = {u'32kb':32768,
                                u'64kb':65536,
                                u'128kb':131072,
                                u'256kb':262144,
                                u'512kb':524288,
                                u'1MB':1048576,
                                u'2MB':2097152,
                                u'4MB':4194304}
        
        
        ##basics
        self.CentreOnScreen()
        frameSizer = wx.BoxSizer(wx.VERTICAL)
        
        mainPanel = wx.Panel(self)
        mainPanelSizer = wx.BoxSizer(wx.VERTICAL)
        mainPanelItems = wx.GridBagSizer(vgap = 0, hgap = 6)
        
        ##files
        fileBox = wx.StaticBox(mainPanel, -1, "Files")
        fileBoxSizer = wx.StaticBoxSizer(fileBox, wx.VERTICAL)
        fileBoxItems = wx.GridBagSizer(vgap = 3, hgap = 5)
        
        #file path
        label = wx.StaticText(mainPanel, -1, "File:")
        label.SetToolTipString('The directory or file for which a torrent should be created.')
        fileBoxItems.Add(label, (0,0), (1,1), wx.ALIGN_CENTER_VERTICAL)

        self.dataPath = wx.TextCtrl(mainPanel, -1, "") 
        self.dataPath.SetToolTipString('The directory or file for which a torrent should be created.')
        fileBoxItems.Add(self.dataPath, (0,1), (1,1), wx.EXPAND | wx.FIXED_MINSIZE)

        buttonId = wx.NewId()
        button = wx.Button(mainPanel, buttonId, "File", style=wx.BU_EXACTFIT)
        button.SetToolTipString('Use this button to select the file for which a torrent should be created.')
        fileBoxItems.Add(button, (0,2), (1,1))
        wx.EVT_BUTTON(self, buttonId, self.OnFilePathFileButton)
        
        buttonId = wx.NewId()
        button = wx.Button(mainPanel, buttonId, "Dir", style=wx.BU_EXACTFIT)
        button.SetToolTipString('Use this button to select the directory for which a torrent should be created.')
        fileBoxItems.Add(button, (0,3), (1,1))
        wx.EVT_BUTTON(self, buttonId, self.OnFilePathDirButton)
        
        #torrent path
        label = wx.StaticText(mainPanel, -1, "Torrent:")
        label.SetToolTipString('The filepath of the torrent file which should be created.')
        fileBoxItems.Add(label, (1,0), (1,1), wx.ALIGN_CENTER_VERTICAL)

        self.torrentPath = wx.TextCtrl(mainPanel, -1, "")
        self.torrentPath.SetToolTipString('The filepath of the torrent file which should be created.')
        fileBoxItems.Add(self.torrentPath, (1,1), (1,1), wx.EXPAND | wx.FIXED_MINSIZE)

        buttonId = wx.NewId()
        button = wx.Button(mainPanel, buttonId, "...", style=wx.BU_EXACTFIT)
        fileBoxItems.Add(button, (1,2), (1,2))
        wx.EVT_BUTTON(self, buttonId, self.OnTorrentPathButton)
        
        #sizer
        fileBoxItems.AddGrowableCol(1, 1)
        fileBoxSizer.Add(fileBoxItems, 1, wx.EXPAND | wx.ALL, border = 2)
        mainPanelItems.Add(fileBoxSizer, (0,0), (1,1), wx.EXPAND | wx.ALL, border = 2)
        
        
        ##other
        otherBox = wx.StaticBox(mainPanel, -1, "Other")
        otherBoxSizer = wx.StaticBoxSizer(otherBox, wx.VERTICAL)
        otherBoxItems = wx.FlexGridSizer(cols = 2, vgap = 3, hgap = 5)
        
        #creation date
        label = wx.StaticText(mainPanel, -1, "Creation date:")
        label.SetToolTipString('Add a creation date to the torrent?')
        otherBoxItems.Add(label, 1, wx.ALIGN_CENTER_VERTICAL)
        
        self.creationDate = wx.CheckBox(mainPanel, -1)
        self.creationDate.SetToolTipString('Add a creation date to the torrent?')
        self.creationDate.SetValue(True)
        otherBoxItems.Add(self.creationDate, 1, wx.EXPAND)
        
        #created by
        label = wx.StaticText(mainPanel, -1, "Created by:")
        label.SetToolTipString("The person or application which created this torrent.")
        otherBoxItems.Add(label, 1, wx.ALIGN_CENTER_VERTICAL)

        self.createdBy = wx.TextCtrl(mainPanel, -1, "PyBit")
        self.createdBy.SetToolTipString("The person or application which created this torrent.")
        otherBoxItems.Add(self.createdBy, 1, wx.EXPAND | wx.FIXED_MINSIZE)
        
        #comment
        label = wx.StaticText(mainPanel, -1, "Comment:")
        label.SetToolTipString("A comment describing this torrent.")
        otherBoxItems.Add(label, 1, wx.ALIGN_CENTER_VERTICAL)

        self.comment = wx.TextCtrl(mainPanel, -1, "")
        self.comment.SetToolTipString("A comment describing this torrent.")
        otherBoxItems.Add(self.comment, 1, wx.EXPAND | wx.FIXED_MINSIZE)
        
        #sizer
        otherBoxItems.AddGrowableCol(1, 1)
        otherBoxSizer.Add(otherBoxItems, 1, wx.EXPAND | wx.ALL, border = 2)
        mainPanelItems.Add(otherBoxSizer, (1,0), (1,1), wx.EXPAND | wx.ALL, border = 2)
        
        
        ##pieces
        pieceBox = wx.StaticBox(mainPanel, -1, "Piece size")
        pieceBoxSizer = wx.StaticBoxSizer(pieceBox, wx.VERTICAL)
        pieceBoxItems = wx.GridBagSizer(vgap = 3, hgap = 20)
        
        #piece size
        label = wx.StaticText(mainPanel, -1, "Piece size:")
        label.SetToolTipString('This determines the size of a single piece of the torrent. A piece is the smallest chunk of data which can '+\
                               'be verified, so smaller sizes are generally better (but the hash for a single piece increases the size of the torrent file ~23 bytes)')
        pieceBoxItems.Add(label, (0,0), (1,1), wx.ALIGN_CENTER_VERTICAL)
        
        comboId = wx.NewId()
        self.pieceSize = wx.ComboBox(mainPanel, comboId, size = wx.Size(85, -1),\
                                     choices=['32kb', '64kb', '128kb', '256kb', '512kb', '1MB', '2MB', '4MB'], style=wx.CB_READONLY)
        self.pieceSize.SetToolTipString('This determines the size of a single piece of the torrent. A piece is the smallest chunk of data which can '+\
                                       'be verified, so in theory a smaller size is better. On the other hand the hash for each piece increases the size of the torrent file 20 bytes.')
        pieceBoxItems.Add(self.pieceSize, (0,1), (1,1))
        wx.EVT_COMBOBOX(self, comboId, self.OnPieceComboSelect)
        
        
        #estimated file size
        label = wx.StaticText(mainPanel, -1, "Size of torrent data:")
        pieceBoxItems.Add(label, (2,0), (1,1))
        
        self.torrentDataSize = wx.StaticText(mainPanel, -1, "0.00B")
        pieceBoxItems.Add(self.torrentDataSize, (2,1), (1,1), wx.EXPAND)
        
        #piece count
        label = wx.StaticText(mainPanel, -1, "Number of pieces:")
        pieceBoxItems.Add(label, (3,0), (1,1))
        
        self.amountOfPieces = wx.StaticText(mainPanel, -1, "0")
        pieceBoxItems.Add(self.amountOfPieces, (3,1), (1,1), wx.EXPAND)
        
        #estimated torrent file size
        label = wx.StaticText(mainPanel, -1, "Size of torrent file:")
        pieceBoxItems.Add(label, (4,0), (1,1))
        
        self.torrentFileSize = wx.StaticText(mainPanel, -1, ">0.00B")
        pieceBoxItems.Add(self.torrentFileSize, (4,1), (1,1), wx.EXPAND)
        
        #update button
        buttonId = wx.NewId()
        self.pieceBoxUpdateButton = wx.Button(mainPanel, buttonId, "Update", style=wx.BU_EXACTFIT)
        pieceBoxItems.Add(self.pieceBoxUpdateButton, (5,0), (1,2), wx.ALIGN_BOTTOM | wx.ALIGN_CENTER_HORIZONTAL)
        wx.EVT_BUTTON(self, buttonId, self.OnPieceStatUpdateButton)
        
        #sizer
        pieceBoxItems.AddGrowableCol(1, 1)
        pieceBoxItems.AddGrowableRow(5, 1)
        pieceBoxSizer.Add(pieceBoxItems, 1, wx.EXPAND | wx.ALL, border = 2)
        mainPanelItems.Add(pieceBoxSizer, (0,1), (2,1), wx.EXPAND | wx.ALL, border = 2)
        
        
        ##tracker
        trackerBox = wx.StaticBox(mainPanel, -1, "Tracker")
        trackerBoxSizer = wx.StaticBoxSizer(trackerBox, wx.VERTICAL)
        trackerBoxItems = wx.GridBagSizer(vgap = 3, hgap = 5)
        
        #tracker url
        boxId = wx.NewId()
        self.trackerName = wx.ComboBox(mainPanel, boxId, size = wx.Size(155, -1),\
                                       choices=['crstrack.i2p', 'tracker.postman.i2p', 'tracker.welterde.i2p', 'other'], style=wx.CB_READONLY)
        self.trackerName.SetToolTipString('Either select one of the predefined trackers here or select "other" to enter a different tracker announce url in the text box to the right')
        trackerBoxItems.Add(self.trackerName, (0,0), (1,1))
        wx.EVT_COMBOBOX(self, boxId, self.OnTrackerNameSelection)
                                    
        self.trackerAnnounceUrl = wx.TextCtrl(mainPanel, -1, "") 
        self.trackerAnnounceUrl.SetToolTipString('The full announce url of the tracker, including the "http://"-prefix.')
        self.trackerAnnounceUrl.Disable()
        trackerBoxItems.Add(self.trackerAnnounceUrl, (0,1), (1,1), wx.EXPAND | wx.FIXED_MINSIZE)
        
        buttonId = wx.NewId()
        buttonAdd = wx.Button(mainPanel, buttonId, "Add", style=wx.BU_EXACTFIT)
        trackerBoxItems.Add(buttonAdd, (0,2), (1,1), wx.EXPAND)
        wx.EVT_BUTTON(self, buttonId, self.OnTrackerUrlAddButton)
        
        
        #tracker list
        listboxId = wx.NewId()
        self.trackerList = wx.ListBox(mainPanel, id=listboxId, style=wx.LB_SINGLE)
        self.trackerList.SetToolTipString('A list of all tracker announce urls which will be included in the torrent. Most clients will try the topmost url first and, if that tracker isn\'t reachable, proceed to try the ones further down the list.')
        trackerBoxItems.Add(self.trackerList, (1,0), (5,2), wx.EXPAND | wx.FIXED_MINSIZE)
        
        buttonId = wx.NewId()
        buttonDel = wx.Button(mainPanel, buttonId, "Remove", style=wx.BU_EXACTFIT)
        trackerBoxItems.Add(buttonDel, (1,2), (1,1), wx.EXPAND)
        wx.EVT_BUTTON(self, buttonId, self.OnTrackerUrlRemoveButton)
        
        buttonId = wx.NewId()
        buttonUp = wx.Button(mainPanel, buttonId, "Move Up", style=wx.BU_EXACTFIT)
        trackerBoxItems.Add(buttonUp, (3,2), (1,1), wx.EXPAND)
        wx.EVT_BUTTON(self, buttonId, self.OnTrackerUrlUpButton)
        
        buttonId = wx.NewId()
        buttonDown = wx.Button(mainPanel, buttonId, "Move Down", style=wx.BU_EXACTFIT)
        trackerBoxItems.Add(buttonDown, (4,2), (1,1), wx.EXPAND)
        wx.EVT_BUTTON(self, buttonId, self.OnTrackerUrlDownButton)
        
        #sizer
        trackerBoxItems.AddGrowableCol(1, 1)
        trackerBoxItems.AddGrowableRow(5, 1)
        trackerBoxSizer.Add(trackerBoxItems, 1, wx.EXPAND | wx.ALL, border = 2)
        mainPanelItems.Add(trackerBoxSizer, (2,0), (1,2), wx.EXPAND | wx.ALL, border = 2)
        
        
        ##progress
        progressBox = wx.StaticBox(mainPanel, -1, "Progress")
        self.progressBoxSizer = wx.StaticBoxSizer(progressBox, wx.VERTICAL)
        progressBoxItems = wx.GridBagSizer(vgap = 3, hgap = 5)
        
        #total
        label = wx.StaticText(mainPanel, -1, "Total:")
        progressBoxItems.Add(label, (0,0), (1,1), wx.ALIGN_CENTER_VERTICAL)
        
        self.totalProgressBar = wx.Gauge(mainPanel, -1)
        self.totalProgressBar.SetValue(0)
        self.totalProgressBar.SetRange(0)
        progressBoxItems.Add(self.totalProgressBar, (0,1), (1,1), wx.EXPAND)
        
        self.totalProgressText = wx.StaticText(mainPanel, -1, "0.00B/0.00B")
        progressBoxItems.Add(self.totalProgressText, (0,2), (1,1), wx.ALIGN_CENTER_VERTICAL)
        
        #current
        label = wx.StaticText(mainPanel, -1, "Current:")
        progressBoxItems.Add(label, (1,0), (1,1), wx.ALIGN_CENTER_VERTICAL)
        
        self.currentProgressBar = wx.Gauge(mainPanel, -1)
        self.currentProgressBar.SetValue(0)
        self.currentProgressBar.SetRange(10000)
        progressBoxItems.Add(self.currentProgressBar, (1,1), (1,1), wx.EXPAND)
        
        self.currentProgressText = wx.StaticText(mainPanel, -1, "0.00%")
        progressBoxItems.Add(self.currentProgressText, (1,2), (1,1), wx.ALIGN_CENTER_VERTICAL)
        
        #file
        label = wx.StaticText(mainPanel, -1, "File:")
        progressBoxItems.Add(label, (2,0), (1,1), wx.ALIGN_CENTER_VERTICAL)
        
        self.currentFileName = wx.StaticText(mainPanel, -1, "")
        progressBoxItems.Add(self.currentFileName, (2,1), (1,1), wx.ALIGN_CENTER_VERTICAL | wx.EXPAND | wx.FIXED_MINSIZE)
        
        self.currentFileProgress = wx.StaticText(mainPanel, -1, "0/0 Files")
        progressBoxItems.Add(self.currentFileProgress, (2,2), (1,1), wx.ALIGN_CENTER_VERTICAL)
        
        
        #sizer
        progressBoxItems.AddGrowableCol(1, 1)
        self.progressBoxSizer.Add(progressBoxItems, 1, wx.EXPAND | wx.ALL, border = 2)
        mainPanelItems.Add(self.progressBoxSizer, (3,0), (1,2), wx.EXPAND | wx.ALL, border = 2)
        
        
        ##buttons
        
        mainPanelButtonItems = wx.GridBagSizer(vgap = 3, hgap = 5)
        
        #create button
        buttonId = wx.NewId()
        self.createButton = wx.Button(mainPanel, buttonId, "Create", style=wx.BU_EXACTFIT)
        mainPanelButtonItems.Add(self.createButton, (0,0), (1,1), wx.ALIGN_CENTER_HORIZONTAL)
        wx.EVT_BUTTON(self, buttonId, self.OnCreateButton)
        
        #cancel button
        buttonId = wx.NewId()
        button = wx.Button(mainPanel, buttonId, "Cancel", style=wx.BU_EXACTFIT)
        mainPanelButtonItems.Add(button, (0,1), (1,1), wx.ALIGN_CENTER_HORIZONTAL)
        wx.EVT_BUTTON(self, buttonId, self.OnCancelButton)
        self.Bind(wx.EVT_CLOSE, self.OnCancelButton)
        
        #sizer
        mainPanelButtonItems.AddGrowableCol(0, 1)
        mainPanelButtonItems.AddGrowableCol(1, 1)
        mainPanelItems.Add(mainPanelButtonItems, (4,0), (1,2), wx.EXPAND | wx.ALL, border = 2)
        
        
        ##main
        mainPanelItems.AddGrowableCol(0, 1)
        mainPanelItems.AddGrowableRow(2, 1)
        mainPanelSizer.Add(mainPanelItems, 1, wx.EXPAND | wx.ALL, border = 2)
        mainPanel.SetSizer(mainPanelSizer)
        
        frameSizer.Add(mainPanel, 1, wx.EXPAND | wx.ALL, border = 0)
        self.SetSizer(frameSizer)
        self.Layout()
        self.Show()
        
        
    ##torrent creation
        
    def _abort(self):
        self.torrentCreator.abort()
        self.torrentCreator.reset()
        self.createButton.SetLabel(u'Create')
        self.pieceBoxUpdateButton.Enable()
        self.updateTimer.Stop()
        self.Update()
        self.progressBoxSizer.Layout()
        
        
    def _updatePieceEstimates(self, totalFileSize):
        if not self.pieceSize.GetValue() == u'':
            pieceSize = self.pieceSizeMapper[self.pieceSize.GetValue()]
            pieceCount = int(math.ceil(totalFileSize / (pieceSize * 1.0)))
            self.torrentDataSize.SetLabel(dataAmountToString(totalFileSize))
            self.amountOfPieces.SetLabel(str(pieceCount))
            self.torrentFileSize.SetLabel('>'+dataAmountToString(pieceCount*20))
            self.Update()
            self.progressBoxSizer.Layout()
            
        
    ##events - files
        
    def OnFilePathFileButton(self, event):
        defaultPath = normalisePath(self.dataPath.GetValue(), expand=True)
        
        if defaultPath == '' or (not os.path.exists(defaultPath)):
            #nothing valid, default
            defaultDir = self.progPath
            defaultFile = ''
        elif os.path.isdir(defaultPath):
            #directory
            defaultDir = defaultPath
            defaultFile = ''
        else:
            #file
            defaultDir = os.path.dirname(defaultPath)
            defaultFile = os.path.basename(defaultPath)
            
        fileSelectDialog = wx.FileDialog(self, message='Select a file',\
                                         defaultDir=defaultDir, defaultFile=defaultFile, wildcard='All files (*.*)|*.*',\
                                         style=wx.OPEN)
                                    
        if fileSelectDialog.ShowModal() == wx.ID_OK:
            #user selected something
            self.dataPath.SetValue(fileSelectDialog.GetPath())
            
    
    def OnFilePathDirButton(self, event):
        defaultPath = normalisePath(self.dataPath.GetValue(), expand=True)
        
        if defaultPath == '' or (not os.path.exists(defaultPath)):
            #nothing valid, default
            defaultPath = self.progPath
        elif os.path.isfile(defaultPath):
            #file
            defaultPath = os.path.dirname(defaultPath)
            
        dirSelectDialog = wx.DirDialog(self, message='Select a directory',\
                                       defaultPath=defaultPath,style=wx.DD_DEFAULT_STYLE)
                                    
        if dirSelectDialog.ShowModal() == wx.ID_OK:
            #user selected something
            self.dataPath.SetValue(dirSelectDialog.GetPath())
            
    
    def OnTorrentPathButton(self, event):
        defaultPath = normalisePath(self.torrentPath.GetValue(), expand=True)
        if not defaultPath == '':
            #already selected a torrent before
            defaultDir = os.path.dirname(defaultPath)
            defaultFile = os.path.basename(defaultPath)
        else:
            #nothing selected yet, try to guess something useable from the data path
            defaultPath = normalisePath(self.dataPath.GetValue(), expand=True)
            if defaultPath == '':
                defaultPath = self.progPath
                
            if os.path.isdir(defaultPath):
                #directory
                defaultFile = os.path.basename(defaultPath)
                if not defaultFile == '':
                    defaultDir = os.path.dirname(defaultPath)
                else:
                    defaultDir = os.path.dirname(defaultPath[:-1])
                    defaultFile = os.path.basename(defaultPath[:-1])
                if not defaultFile == '':
                    defaultFile += '.torrent'
            else:
                #file
                defaultDir = os.path.dirname(defaultPath)
                defaultFile = os.path.basename(defaultPath)+'.torrent'
        
        fileSelectDialog = wx.FileDialog(self, message='Save Torrent',\
                                         defaultDir=defaultDir, defaultFile=defaultFile,\
                                         wildcard='Torrent files (*.torrent)|*.torrent|All files (*.*)|*.*',\
                                         style=wx.SAVE | wx.OVERWRITE_PROMPT)
                                    
        if fileSelectDialog.ShowModal() == wx.ID_OK:
            #user selected something
            self.torrentPath.SetValue(fileSelectDialog.GetPath())
    
    
    ##events - pieces
    
    def OnPieceComboSelect(self, event):
        if not self.dataPath.GetValue() == u'':
            stats = self.torrentCreator.getStats()
            self._updatePieceEstimates(stats['totalFileSize'])
            
    
    def OnPieceStatUpdateButton(self, event):
        if self.dataPath.GetValue() == u'':
            showErrorMessage(self, u'The path to the file or directory, for which a torrent should be created, is not set! (field "Files>File")')
            
        elif self.pieceSize.GetValue() == u'':
            showErrorMessage(self, u'There is no piece size selected! (field "Piece size > Piece size")')
            
        else:
            try:
                self.torrentCreator.getFiles(self.dataPath.GetValue())
                stats = self.torrentCreator.getStats()
                self._updatePieceEstimates(stats['totalFileSize'])
                
            except TorrentCreatorException, tce:
                showErrorMessage(self, u'%s', tce.reason)
                
    
    
    ##events - tracker
    
    def OnTrackerNameSelection(self, event):
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
                    
    
    def OnTrackerUrlAddButton(self, event):
        trackerUrl = self.trackerAnnounceUrl.GetValue()
        if not trackerUrl == '':
            if self.trackerList.FindString(trackerUrl) == wx.NOT_FOUND:
                #not in the list, add it
                self.trackerList.Append(trackerUrl)
                
    
    def OnTrackerUrlRemoveButton(self, event):
        selectedUrlIdx = self.trackerList.GetSelection()
        if not selectedUrlIdx == wx.NOT_FOUND:
            self.trackerList.Delete(selectedUrlIdx)
            
    
    def OnTrackerUrlUpButton(self, event):
        selectedUrlIdx = self.trackerList.GetSelection()
        if not selectedUrlIdx == wx.NOT_FOUND:
            if not selectedUrlIdx == 0:
                selectedUrlText = self.trackerList.GetString(selectedUrlIdx)
                self.trackerList.Delete(selectedUrlIdx)
                self.trackerList.Insert(selectedUrlText, selectedUrlIdx - 1)
                self.trackerList.SetSelection(selectedUrlIdx - 1)
                
    
    def OnTrackerUrlDownButton(self, event):
        selectedUrlIdx = self.trackerList.GetSelection()
        if not selectedUrlIdx == wx.NOT_FOUND:
            if not selectedUrlIdx == self.trackerList.GetCount() - 1:
                selectedUrlText = self.trackerList.GetString(selectedUrlIdx)
                self.trackerList.Delete(selectedUrlIdx)
                self.trackerList.Insert(selectedUrlText, selectedUrlIdx + 1)
                self.trackerList.SetSelection(selectedUrlIdx + 1)
    
    
    ##events - main
    
    def OnCreateButton(self, event):
        if self.createButton.GetLabel() == u'Abort':
            #currently creating a torrent, abort
            self._abort()
            
        else:
            #not creating a torrent, create one
            if self.dataPath.GetValue() == u'':
                showErrorMessage(self, u'The path to the file or directory, for which a torrent should be created, is not set! (field "Files>File")')
                
            elif self.torrentPath.GetValue() == u'':
                showErrorMessage(self, u'The filepath for the torrent, which should be created, is not set! (field "Files>Torrent")')
                
            elif self.pieceSize.GetValue() == u'':
                showErrorMessage(self, u'There is no piece size selected! (field "Piece size > Piece size")')
                
            elif self.trackerList.GetCount() == 0:
                showErrorMessage(self, u'There is no tracker configured but at least one is required! (box "Tracker")')
                
            else:
                #everything ok or at least useable, get values
                torrentPath = self.torrentPath.GetValue()
                dataPath = self.dataPath.GetValue()
                pieceSize = self.pieceSizeMapper[self.pieceSize.GetValue()]
                mainTracker = self.trackerList.GetString(0)
                
                if self.trackerList.GetCount() > 1:
                    trackerList = [[trackerUrl] for trackerUrl in self.trackerList.GetStrings()]
                else:
                    trackerList = None
                    
                if self.creationDate.GetValue() == True:
                    creationDate = int(round(time(),0))
                else:
                    creationDate = None
                
                createdBy = self.createdBy.GetValue()
                if createdBy == '':
                    createdBy = None
                    
                comment = self.comment.GetValue()
                if comment == '':
                    comment = None
                
                #start torrent creation
                self.torrentCreator.create(torrentPath, dataPath, pieceSize, mainTracker, trackerList, creationDate, comment, createdBy)
                
                #disable update button
                self.pieceBoxUpdateButton.Disable()
                
                #adjust button label
                self.createButton.SetLabel(u'Abort')
                self.Update()
                self.progressBoxSizer.Layout()
                
                #start timer
                self.updateTimer.Start(250)
            
    
    def OnCancelButton(self, event):
        if self.createButton.GetLabel() == u'Abort':
            #currently creating a torrent, abort
            self._abort()
        self.Destroy()
        
        
    ##events - update
    
    def OnTimer(self, event):
        stats = self.torrentCreator.getStats()
        processed, total = scaleInt(10000, stats['processedFileSize'], stats['totalFileSize'])
        self.totalProgressBar.SetRange(total)
        self.totalProgressBar.SetValue(processed)
        self.totalProgressText.SetLabel('%s/%s' % (dataAmountToString(stats['processedFileSize']).strip(), dataAmountToString(stats['totalFileSize'])))
        self.currentProgressBar.SetValue(round(stats['currentFileProgress']*10000, 0))
        self.currentProgressText.SetLabel('%.2f' % (round(stats['currentFileProgress']*100, 2))+'%')
        self.currentFileName.SetLabel(stats['currentFileName'])
        self.currentFileProgress.SetLabel('%i/%i Files' % (stats['currentFileNumber'], stats['amountOfFiles']))
        self.Update()
        self.progressBoxSizer.Layout()
        
        self._updatePieceEstimates(stats['totalFileSize'])
        
        if not self.torrentCreator.isRunning():
            #finished
            self.createButton.SetLabel(u'Create')
            self.pieceBoxUpdateButton.Enable()
            self.Update()
            self.progressBoxSizer.Layout()
            self.updateTimer.Stop()
            
            lastError = self.torrentCreator.getLastError()
            if lastError is None:
                #creation succeeded
                showInfoMessage(self, u'The torrent was successfuly created.')
            else:
                #creation failed
                showErrorMessage(self, u'The creation of the torrent failed:\n%s', lastError.reason)
            self.torrentCreator.reset()
        
        
if __name__ == '__main__':
    #create GUI
    app = wx.App()
    merk = TorrentCreateDialog(os.getcwdu(), None)
    app.MainLoop()