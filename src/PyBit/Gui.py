"""
Copyright 2009  Blub

Gui, a class which, as the name already implies, initialises the GUI of PyBit.
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
import logging
import os
import wx

##own - GUI
from About import About
from ConfigDialog import ConfigDialog
from TorrentConnectionList import TorrentConnectionList
from TorrentCreateDialog import TorrentCreateDialog
from TorrentFileList import TorrentFileList
from TorrentList import TorrentList
from TorrentRequestList import TorrentRequestList
from TorrentStats import TorrentStats
from TorrentTrackerList import TorrentTrackerList
from ScrollableTextViewer import ScrollableTextViewerFrame
from StatusBar import StatusBar
from StatusPanel import StatusPanel

##own - other
from Bittorrent.MultiBt import MultiBtException
from Utilities import logTraceback, showWarningMessage, showErrorMessage, FunctionCallConverter


class Gui(wx.Frame):
    def __init__(self, progPath, config, torrentHandler, persister, version):
        self.progPath = progPath
        self.config = config
        self.torrentHandler = torrentHandler
        self.persister = persister
        self.version = version
        
        self.log = logging.getLogger("Gui")
        self.stopFlag = False
        
        ##locale
        self.locale = wx.Locale(wx.LANGUAGE_ENGLISH)
        
        
        ##Gui Stuff
        wx.Frame.__init__(self, None, -1, 'PyBit', size = wx.Size(800, 600), style = wx.DEFAULT_FRAME_STYLE | wx.CLIP_CHILDREN)
        self.CentreOnScreen()
        
        #Layoutmanager
        vBox = wx.BoxSizer(wx.VERTICAL)
        
        #Menu
        menubar = wx.MenuBar()
        
        file = wx.Menu()
        file.Append(101, 'Add (by File)', 'Opens a torrent from your harddisk')
        file.Append(102, 'Add (by Url)', 'Fetches a torrent via http and adds it afterwards')
        file.AppendSeparator()
        file.Append(103, 'Create', 'Creates a new torrent')
        file.AppendSeparator()
        file.Append(104, 'Quit', 'Terminates the program, this could take a few seconds')
        menubar.Append(file, '&File')

        config = wx.Menu()
        config.Append(121, 'Configuration', 'Opens a configuration dialog')
        menubar.Append(config, '&Config')
        about = wx.Menu()
        about.Append(131, 'About', 'Information about the version and the authors of this software')
        about.Append(132, 'Show Changelog', 'Shows the changlog of PyBit')
        about.Append(133, 'Show Readme', 'Shows the readme')
        menubar.Append(about, '&About')
        
        self.SetMenuBar(menubar)
        
        #Windows
        self.splitter = wx.SplitterWindow(self, style=wx.CLIP_CHILDREN)
        self.splitter.SetMinimumPaneSize(50)
        
        #Child Windows
        self.childWindows = StatusPanel(self.splitter)        
        self.torrentStats = TorrentStats(self.torrentHandler.getStats, self.childWindows)
        self.torrentConnectionList = TorrentConnectionList(self.persister, self.version, self.torrentHandler.getStats, self.childWindows)
        self.torrentFileList = TorrentFileList(self.persister, self.version, self.torrentHandler.getStats, self.torrentHandler.setFilePriority, self.torrentHandler.setFileWantedFlag, self.childWindows)
        self.torrentRequestList = TorrentRequestList(self.persister, self.version, self.torrentHandler.getStats, self.childWindows)
        self.torrentTrackerList = TorrentTrackerList(self.persister, self.version, self.torrentHandler.getStats, self.torrentHandler.getTrackerInfo, self.torrentHandler.setTrackerInfo, self.childWindows)
        self.childWindows.addChild(self.torrentStats, 'General')
        self.childWindows.addChild(self.torrentConnectionList, 'Connections')
        self.childWindows.addChild(self.torrentFileList, 'Files')
        self.childWindows.addChild(self.torrentRequestList, 'Requests')
        self.childWindows.addChild(self.torrentTrackerList, 'Tracker')
        
        #Main Window
        self.torrentList = TorrentList(self.persister, self.version, self.torrentHandler, self.childWindows.changeTorrentId, self.torrentHandler.getStats, self.splitter)

        #startup the splitter
        self.splitter.SplitHorizontally(self.torrentList, self.childWindows)
        
        #Statusbar
        funcCaller = FunctionCallConverter(self.torrentHandler.getStats, funcKw={'wantedStats':{'transfer':True}},
                                           resultFilter=['inRawSpeed', 'outRawSpeed'], resultFilterFormat='list')
        self.sb = StatusBar(funcCaller.callForValue, self)
        self.SetStatusBar(self.sb)
        
        #Toolbar
        toolbar = self.CreateToolBar()
        toolbar.SetToolBitmapSize(wx.Size(22,22))
        toolbar.AddLabelTool(201, 'New', wx.BitmapFromImage(wx.Image('Icons/newFile.png', wx.BITMAP_TYPE_PNG)), shortHelp='Create Torrentfile', longHelp='Use to create a new torrent file')
        toolbar.AddLabelTool(202, 'Open File', wx.BitmapFromImage(wx.Image('Icons/openFile.png', wx.BITMAP_TYPE_PNG)), shortHelp='Open Torrentfile', longHelp='Use to open a torrent file')
        toolbar.AddLabelTool(203, 'Open Url', wx.BitmapFromImage(wx.Image('Icons/openUrl.png', wx.BITMAP_TYPE_PNG)), shortHelp='Fetch and open Torrentfile from url', longHelp='Use to fetch (and add) a torrent file via http')
        toolbar.AddSeparator()
        toolbar.AddLabelTool(211, 'Start',wx.BitmapFromImage(wx.Image('Icons/start.png', wx.BITMAP_TYPE_PNG)), shortHelp='Start', longHelp='Starts all selected torrents')
        toolbar.AddLabelTool(212, 'Stop',wx.BitmapFromImage(wx.Image('Icons/stop.png', wx.BITMAP_TYPE_PNG)), shortHelp='Stop', longHelp='Stops all selected torrents')
        toolbar.AddLabelTool(213, 'Remove',wx.BitmapFromImage(wx.Image('Icons/remove.png', wx.BITMAP_TYPE_PNG)), shortHelp='Remove', longHelp='Removes all selected torrents')
        toolbar.AddSeparator()
        toolbar.AddLabelTool(221, 'Up',wx.BitmapFromImage(wx.Image('Icons/up.png', wx.BITMAP_TYPE_PNG)), shortHelp='Up', longHelp='Moves all selected torrents one row up')
        toolbar.AddLabelTool(222, 'Down',wx.BitmapFromImage(wx.Image('Icons/down.png', wx.BITMAP_TYPE_PNG)), shortHelp='Down', longHelp='Moves all selected torrents one row down')
        toolbar.AddSeparator()
        toolbar.AddLabelTool(231, 'Quit', wx.BitmapFromImage(wx.Image('Icons/quit.png', wx.BITMAP_TYPE_PNG)), shortHelp='Quit', longHelp='Quits the application, this could take a moment.')
        toolbar.Realize()

        #menu events
        self.Bind(wx.EVT_MENU, self.OnAddFromFile, id=101)
        self.Bind(wx.EVT_MENU, self.OnAddFromUrl, id=102)
        self.Bind(wx.EVT_MENU, self.OnCreateTorrent, id=103)
        self.Bind(wx.EVT_MENU, self.OnClose, id=104)
        self.Bind(wx.EVT_MENU, self.OnConfig, id=121)
        self.Bind(wx.EVT_MENU, self.OnAbout, id=131)
        self.Bind(wx.EVT_MENU, self.OnChangelog, id=132)
        self.Bind(wx.EVT_MENU, self.OnReadme, id=133)

        #toolbar events
        self.Bind(wx.EVT_TOOL, self.OnCreateTorrent, id=201)
        self.Bind(wx.EVT_TOOL, self.OnAddFromFile, id=202)
        self.Bind(wx.EVT_TOOL, self.OnAddFromUrl, id=203)
        self.Bind(wx.EVT_TOOL, self.torrentList.OnStart, id=211)
        self.Bind(wx.EVT_TOOL, self.torrentList.OnStop, id=212)
        self.Bind(wx.EVT_TOOL, self.torrentList.OnRemove, id=213)
        self.Bind(wx.EVT_TOOL, self.torrentList.OnUp, id=221)
        self.Bind(wx.EVT_TOOL, self.torrentList.OnDown, id=222)
        self.Bind(wx.EVT_TOOL, self.OnClose, id=231)
        
        #other events
        self.Bind(wx.EVT_CLOSE, self.OnClose)

        self.Show(True)
        
        #updater
        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.OnTimer, self.timer)
        self.timer.Start(1000)


    def OnTimer(self, event):
        try:
            if not self.stopFlag:
                #update Torrentlist
                self.torrentList.manualUpdate()
                self.childWindows.manualUpdate()

                #update Statusbar
                self.sb.manualUpdate()
        except:
            self.log.error("Failure in timer:\n%s", logTraceback())
            

    def OnAddFromFile(self, event):
        #torrentpath
        torrentDefaultDir = self.config.get('paths','torrentFolder')
        downloadDefaultDir = self.config.get('paths','downloadFolder')
        
        #let user select a torrent
        diag = wx.FileDialog(self, message='Select the torrent to open',defaultDir=torrentDefaultDir,\
                             wildcard='Torrent files (*.torrent)|*.torrent|All files (*.*)|*.*',\
                             style=wx.OPEN | wx.MULTIPLE)
        
        if diag.ShowModal() == wx.ID_OK:
            #user did select something
            torrentPaths = diag.GetPaths()
            
            #directory in which the download data should be stored
            saveDiag = wx.DirDialog(self, message='Select the directory in which the downloaded data should be stored',\
                                    defaultPath=downloadDefaultDir,style=wx.DD_NEW_DIR_BUTTON)
            if saveDiag.ShowModal() == wx.ID_OK:
                #user selected something
                savePath = saveDiag.GetPath()
                
                #load torrents one by one
                for torrentPath in torrentPaths:
                    self.log.info('Trying to read torrent file from "%s"', torrentPath)
                    try:
                        fl = open(torrentPath, 'rb')
                        with fl:
                            data = fl.read()
                    except (IOError, OSError):
                        data = None
                    
                    if data is None:
                        #failed to read file
                        self.log.error('Failed to read torrent file from "%s", torrent not added', torrentPath)
                        showErrorMessage(self, 'Failed to read torrent file from "%s".', torrentPath)
                    else:
                        #worked
                        self.log.info('Adding torrent with data path "%s"', savePath)
                        try:
                            self.torrentList.addTorrentByFile(data, savePath)
                        except MultiBtException, e:
                            self.log.error('Failed to add torrent, reason: %s', e.reason)
                            showErrorMessage(self, '%s.', e.reason)
                        except Exception, e:
                            self.log.critical('Internal error while adding torrent:\n%s', logTraceback())
                            showErrorMessage(self, 'Internal error, torrent not added.\n%s.', logTraceback())
            del saveDiag
        del diag
        
        
    def OnAddFromUrl(self, event):
        #torrentpath
        downloadDefaultDir = self.config.get('paths','downloadFolder')
        
        #let user enter a url
        diag = wx.TextEntryDialog(self, message='Please enter the http url of the torrent file:', caption='Enter url', defaultValue='http://')
        
        if diag.ShowModal() == wx.ID_OK:
            #user did select something
            torrentUrl = diag.GetValue()
            
            #directory in which the download data should be stored
            saveDiag = wx.DirDialog(self, message='Select the directory in which the downloaded data should be stored',\
                                    defaultPath=downloadDefaultDir, style=wx.DD_NEW_DIR_BUTTON)
            if saveDiag.ShowModal() == wx.ID_OK:
                #user selected something
                savePath = saveDiag.GetPath()
                
                #load torrents one by one
                self.log.info('Adding torrent with data path "%s"', savePath)
                try:
                    self.torrentList.addTorrentByUrl(torrentUrl, savePath)
                except MultiBtException, e:
                    self.log.error('Failed to add torrent, reason: %s', e.reason)
                    showErrorMessage(self, '%s.', e.reason)
                except Exception, e:
                    self.log.critical('Internal error while adding torrent:\n%s', logTraceback())
                    showErrorMessage(self, 'Internal error, torrent not added.\n%s.', logTraceback())
            del saveDiag
        del diag
        
        
    def OnCreateTorrent(self, event):
        TorrentCreateDialog(self.progPath, self)
        

    def OnConfig(self, event):
        ConfigDialog(self.config, self)
        

    def OnAbout(self, event):
        About(self, self.version)
        

    def OnChangelog(self, event):
        ScrollableTextViewerFrame(self, 'Changelog', os.path.join(self.progPath, u'changelog'))
        
    
    def OnReadme(self, event):
        ScrollableTextViewerFrame(self, 'Readme', os.path.join(self.progPath, u'readme'))
        

    def OnClose(self, event):
        self.stopFlag = True
        self.Destroy()




def showGui(path, config, torrentHandler, persister, version):
    app = wx.App()
    test = Gui(path, config, torrentHandler, persister, version)
    try:
        app.MainLoop()
    except:
        print 'Main loop failed:', str(logTraceback())