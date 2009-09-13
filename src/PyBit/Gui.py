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

##own - GUI
from About import About
from ChangelogViewer import ChangelogViewer
from ConfigDialog import ConfigDialog
from TorrentConnectionList import TorrentConnectionList
from TorrentList import TorrentList
from TorrentStats import TorrentStats
from StatusBar import StatusBar
from StatusPanel import StatusPanel
from SortableList import SortableList

##own - other
from Bittorrent.MultiBt import MultiBt, VERSION
from Config import Config
from ObjectPersister import ObjectPersister
from Utilities import logTraceback, FunctionCallConverter

##other
from time import time, sleep
import logging
import os
import wx


class Gui(wx.Frame):
    def __init__(self, progPath):
        self.progPath = progPath
        self.stopFlag = False
        
        #objects
        self.log = logging.getLogger('Gui')
        self.log.info("Creating object persister instance")
        self.persister = ObjectPersister(os.path.join(progPath, u'state.db'), log='ObjectPersister')
        
        #create config, set defaults
        configDefaults = {'logging':{'loglevel':('Info', 'str')},
                          'paths'  :{'torrentFolder':(progPath, 'str'),
                                     'downloadFolder':(progPath, 'str')}}
        self.config = Config(os.path.join(progPath, u'config.conf'), configDefaults=configDefaults)
        
        self.torrentHandler = MultiBt(self.config, self.persister, self.progPath)
        
        
        #Gui Stuff
        wx.Frame.__init__(self, None, -1, 'PyBit', size = wx.Size(800, 600), style = wx.DEFAULT_FRAME_STYLE)
        self.CentreOnScreen()
        
        #Layoutmanager
        vBox = wx.BoxSizer(wx.VERTICAL)
        
        #Menu
        menubar = wx.MenuBar()
        
        file = wx.Menu()        
        file.Append(101, 'Quit', 'Terminates the program, this could take a few seconds')
        menubar.Append(file, '&File')

        torrents = wx.Menu()
        torrents.Append(111, 'Add from File', 'Opens a torrent from your harddisk')
        #torrents.Append(112, 'Add from URL', 'Opens a torrent from a http url')
        torrents.AppendSeparator()
        torrents.Append(113, 'Start selected', 'Starts all selected torrents which are currently stopped')
        torrents.Append(114, 'Stop selected', 'Stops all selected torrents which are currently running')
        torrents.Append(115, 'Remove selected', 'Removes all selected torrents which are already stopped')
        torrents.AppendSeparator()
        torrents.Append(116, 'Move selected up', 'Moves all selected torrents one row up')
        torrents.Append(117, 'Move selected down', 'Moves all selected torrents one row down')
        menubar.Append(torrents, '&Torrent')

        config = wx.Menu()
        config.Append(121, 'Configuration', 'Opens a configuration dialog')
        menubar.Append(config, '&Config')
        about = wx.Menu()
        about.Append(131, 'About', 'Information about the version and the authors of this software')
        about.Append(132, 'Show Changelog', 'Show the changlog of the bt client and the GUI')
        menubar.Append(about, '&About')
        
        self.SetMenuBar(menubar)

        #Toolbar
        #wx.ToolBar(self, -1, style=wx.TB_HORIZONTAL | wx.NO_BORDER)
        toolbar = self.CreateToolBar()
        toolbar.SetToolBitmapSize(wx.Size(22,22))
        toolbar.AddLabelTool(201, 'Open', wx.BitmapFromImage(wx.Image('Icons/openFile.png', wx.BITMAP_TYPE_PNG)), shortHelp='Open Torrentfile', longHelp='Use to open a torrent file')
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
        
        #Windows
        self.splitter = wx.SplitterWindow(self)
        
        #Child Windows
        self.childWindows = StatusPanel(self.splitter)        
        self.torrentStats = TorrentStats(self.torrentHandler.getStats, self.childWindows)
        self.torrentConnectionList = TorrentConnectionList(self.torrentHandler.getStats, self.childWindows)
        self.childWindows.addChild(self.torrentStats, 'General')
        self.childWindows.addChild(self.torrentConnectionList, 'Connections')
        
        #Main Window
        self.torrentList = TorrentList(self.torrentHandler, self.childWindows.changeTorrentId, self.torrentHandler.getStats, self.splitter)

        #startup the splitter
        self.splitter.SplitHorizontally(self.torrentList, self.childWindows)
        
        #Statusbar
        funcCaller = FunctionCallConverter(self.torrentHandler.getStats, funcKw={'wantedStats':{'transfer':True}},
                                           resultFilter=['inRawSpeed', 'outRawSpeed'], resultFilterFormat='list')
        self.sb = StatusBar(funcCaller.callForValue, self)
        self.SetStatusBar(self.sb)

        #menu events
        self.Bind(wx.EVT_MENU, self.OnClose, id=101)
        self.Bind(wx.EVT_MENU, self.OnAddFromFile, id=111)
        #self.Bind(wx.EVT_MENU, self.OnAddFromURL, id=112)
        self.Bind(wx.EVT_MENU, self.torrentList.OnStart, id=113)
        self.Bind(wx.EVT_MENU, self.torrentList.OnStop, id=114)
        self.Bind(wx.EVT_MENU, self.torrentList.OnRemove, id=115)
        self.Bind(wx.EVT_MENU, self.torrentList.OnUp, id=116)
        self.Bind(wx.EVT_MENU, self.torrentList.OnDown, id=117)
        self.Bind(wx.EVT_MENU, self.OnConfig, id=121)
        self.Bind(wx.EVT_MENU, self.OnAbout, id=131)
        self.Bind(wx.EVT_MENU, self.OnChangelog, id=132)

        #toolbar events        
        self.Bind(wx.EVT_TOOL, self.OnAddFromFile, id=201)
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
                self.torrentStats.manualUpdate()
                self.torrentConnectionList.manualUpdate()

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
                             style=wx.OPEN)
        
        if diag.ShowModal() == wx.ID_OK:
            #user did select something
            torrentPath = diag.GetPath()
            
            #directory in which the download data should be stored
            saveDiag = wx.DirDialog(self, message='Select the directory in which the downloaded data should be stored',\
                                    defaultPath=downloadDefaultDir,style=wx.DD_NEW_DIR_BUTTON)
            if saveDiag.ShowModal() == wx.ID_OK:
                #user selected something
                savePath = saveDiag.GetPath()
                
                #try to load torrent
                self.log.info('Trying to read torrent file from "%s"', torrentPath)
                try:
                    fl = open(torrentPath, 'rb')
                    data = fl.read()
                    fl.close()
                except:
                    data = None
                
                if data is None:
                    #failed to read file
                    self.log.error('Failed to read torrent file from "%s", torrent not added', torrentPath)
                else:
                    #worked
                    self.log.info('Adding torrent with data path "%s"', savePath)
                    self.torrentList.addTorrent(data, savePath)
            del saveDiag
        del diag

##    def OnAddFromURL(self, event):
##        pass


    def OnConfig(self, event):
        ConfigDialog(self.config, self)
        

    def OnAbout(self, event):
        About(self, VERSION)
        

    def OnChangelog(self, event):
        ChangelogViewer(self, os.path.join(self.progPath, u'changelog'))
        

    def OnClose(self, event):
        self.stopFlag = True
        self.Destroy()
        self.torrentHandler.stop()


if __name__=="__main__":
    import logging
    logging.basicConfig(level=logging.INFO,
                        filename="log",
                        format='%(asctime)s %(levelname)-8s %(name)-22s - %(message)s')

    log = logging.getLogger('main')    
    app = wx.App()
    test = Gui(os.getcwdu())
    try:
        app.MainLoop()
    except:
        log.error(str(logTraceback()))
    logging.shutdown()
