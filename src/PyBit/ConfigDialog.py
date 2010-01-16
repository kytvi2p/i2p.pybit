"""
Copyright 2009  Blub

ConfigDialog, a class which creates a dialog which allows configuring PyBit.
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

import os
import wx
from wx.lib.masked import NumCtrl, IpAddrCtrl


class Choker_ConfigPanel(wx.Panel):
    def __init__(self, config, parent, **kwargs):
        wx.Panel.__init__(self, parent, **kwargs)
        self.config = config
        #stuff
        vBox = wx.BoxSizer(wx.VERTICAL)

        #build up boxes
        chokerBox = wx.StaticBox(self, -1, "Choker")
        chokerBoxSizer = wx.StaticBoxSizer(chokerBox, wx.VERTICAL)
        chokerBoxItems = wx.FlexGridSizer(cols = 1, vgap = 3, hgap = 5)

        commentBox = wx.StaticBox(self, -1, "Note")
        commentBoxSizer = wx.StaticBoxSizer(commentBox, wx.VERTICAL)

        #build choker box
        chokerItems = wx.FlexGridSizer(cols = 2, vgap = 3, hgap = 5)
        chokerItems.AddGrowableCol(0, 1)
        
        ##general
        #interval     
        label = wx.StaticText(self, -1, "Choke interval (seconds):")
        label.SetToolTipString('The set interval determines how often the choker runs to choke and unchoke connections.')
        chokerItems.Add(label, 1, wx.ALIGN_CENTER_VERTICAL)
        
        self.spin1 = wx.SpinCtrl(self, -1, size=wx.Size(80,-1))
        self.spin1.SetRange(60, 300)
        self.spin1.SetValue(self.config.getInt('choker','chokeInterval'))
        self.spin1.SetToolTipString('The set interval determines how often the choker runs to choke and unchoke connections.')
        chokerItems.Add(self.spin1, 1)
        
        
        ##slots
        chokerSlotsBox = wx.StaticBox(self, -1, "Slots")
        chokerSlotsBoxSizer = wx.StaticBoxSizer(chokerSlotsBox, wx.VERTICAL)
        chokerSlotsBoxItems = wx.GridBagSizer(vgap = 3, hgap = 5)
        chokerSlotsBoxItems.AddGrowableCol(1, 1)
            
        #limit scope
        label = wx.StaticText(self, -1, "Scope of limit:")
        label.SetToolTipString('Determines if each torrent gets the configured number of slots or if they are spread over all torrents.')
        chokerSlotsBoxItems.Add(label, (0,0), (1,2), wx.ALIGN_CENTER_VERTICAL)
        
        self.combo1 = wx.ComboBox(self, -1, size = wx.Size(85, -1),\
                                  choices=["Global", "Torrent"], style=wx.CB_READONLY)
        if self.config.get('choker', 'slotLimitScope').lower() == 'torrent':
            self.combo1.SetValue('Torrent')
        else:
            self.combo1.SetValue('Global')
        self.combo1.SetToolTipString('Determines if each torrent gets the configured slots or if they are spread over all torrents.')
        chokerSlotsBoxItems.Add(self.combo1, (0,2), (1,1))
        
        #slot limit
        label = wx.StaticText(self, -1, "Slots:")
        label.SetToolTipString('How many connections may be unchoked (uploaded to) at once?')
        chokerSlotsBoxItems.Add(label, (1,0), (1,2), wx.ALIGN_CENTER_VERTICAL)
        
        self.spin2 = wx.SpinCtrl(self, -1, size=wx.Size(80,-1))
        self.spin2.SetRange(2, 1048576)
        self.spin2.SetValue(self.config.getInt('choker','maxSlots'))
        self.spin2.SetToolTipString('How many connections may be unchoked (uploaded to) at once?')
        chokerSlotsBoxItems.Add(self.spin2, (1,2), (1,1))
        
        #random slot ratio
        label = wx.StaticText(self, -1, "Random slots:")
        label.SetToolTipString('How many slots should be used for random-unchoking?')
        chokerSlotsBoxItems.Add(label, (2,0), (1,1), wx.ALIGN_CENTER_VERTICAL)
        
        self.slide = wx.Slider(self, style=wx.SL_AUTOTICKS | wx.SL_HORIZONTAL)
        self.slide.SetToolTipString('How many slots should be used for random-unchoking?')
        self.slide.SetRange(1,50)
        self.slide.SetValue(int(round(self.config.get('choker','randomSlotRatio')*100, 0)))
        chokerSlotsBoxItems.Add(self.slide, (2,1), (1,1), wx.EXPAND | wx.LEFT, border=10)
        
        self.sliderLabel = wx.StaticText(self, -1, "0 Slots (1%)")
        self.sliderLabel.SetToolTipString('How many slots should be used for random-unchoking?')
        chokerSlotsBoxItems.Add(self.sliderLabel, (2,2), (1,1), wx.ALIGN_CENTER_VERTICAL)
        
        #add item sizer to box sizer
        chokerSlotsBoxSizer.Add(chokerSlotsBoxItems, 1, wx.EXPAND | wx.ALL, border = 5)
        
        ##comment
        #build up comment box 
        commentLabel = wx.StaticText(self, -1, 'Random slots are used to unchoke peers randomly, without considering '+\
                                               'the transfer statistics (how much they uploaded to us etc.). Even peers '+\
                                               'which don\'t have anything interesting may get randomly unchoked.'+\
                                               '\n\n'+\
                                               'These slots are both necessary to find new good peers and to give peers '+\
                                               'without any finished piece a chance to get one. But of course having too many '+\
                                               'of them will reduce the effectiveness of the choker and lead to lower transfer rates.')
        
        commentBoxSizer.Add(commentLabel, 1, flag = wx.EXPAND | wx.ALL, border = 5)
        
        ##main
        #build up choker box
        chokerBoxItems.Add(chokerItems, 1, wx.EXPAND | wx.ALL, border = 5)
        chokerBoxItems.Add(chokerSlotsBoxSizer, 1, wx.EXPAND | wx.ALL, border = 0)
        chokerBoxItems.Add(commentBoxSizer, 1, wx.EXPAND | wx.ALL, border = 0)
        chokerBoxItems.AddGrowableCol(0, 1)
        chokerBoxItems.AddGrowableRow(2, 1)
        chokerBoxSizer.Add(chokerBoxItems, 1, wx.EXPAND | wx.ALL, border = 0)

        vBox.Add(chokerBoxSizer, 1, wx.EXPAND | wx.ALL, border = 2)
        
        #Line everythign up
        self.SetSizer(vBox)
        self.Layout()
        self.UpdateSliderLabel(None)
        
        ##events
        wx.EVT_SLIDER(self, self.slide.GetId(), self.UpdateSliderLabel)
        wx.EVT_SPINCTRL(self, self.spin2.GetId(), self.UpdateSliderLabel)
        
        
    def UpdateSliderLabel(self, event):
        maxSlots = self.spin2.GetValue()
        randomRatio = self.slide.GetValue() / 100.0
        randomSlots = max(1, int(maxSlots * randomRatio))
        self.sliderLabel.SetLabel('%i Slots (%i%%)' % (randomSlots, self.slide.GetValue()))
        self.Update()
        self.Layout()
        

    def saveConfig(self, optionDict):
        optionDict[('choker','chokeInterval')] = self.spin1.GetValue()
        optionDict[('choker','slotLimitScope')] = str(self.combo1.GetValue().lower())
        optionDict[('choker','maxSlots')] = self.spin2.GetValue()
        optionDict[('choker','randomSlotRatio')] = self.slide.GetValue() / 100.0
        
        
        
        
class Logging_ConfigPanel(wx.Panel):
    def __init__(self, config, parent, **kwargs):
        wx.Panel.__init__(self, parent, **kwargs)
        self.config = config
        #stuff
        vBox = wx.BoxSizer(wx.VERTICAL)

        #build up boxes
        loggingBox = wx.StaticBox(self, -1, "Logging")
        loggingBoxSizer = wx.StaticBoxSizer(loggingBox, wx.VERTICAL)
        loggingBoxItems = wx.FlexGridSizer(cols = 1, vgap = 3, hgap = 5)

        commentBox = wx.StaticBox(self, -1, "Note")
        commentBoxSizer = wx.StaticBoxSizer(commentBox, wx.VERTICAL)

        #build speedLimiter box        
        loggingItems = wx.FlexGridSizer(cols = 2, vgap = 3, hgap = 5)
        
        #down speed        
        label1a = wx.StaticText(self, -1, "Console loglevel:")
        label1a.SetToolTipString('Determines the minimum loglevel a logmessage must have to be printed to the console.')
        loggingItems.Add(label1a, 1, wx.EXPAND | wx.ALIGN_CENTER_VERTICAL)
        
        self.combo1 = wx.ComboBox(self, -1, size = wx.Size(85, -1),\
                                  choices=["Critical", "Error", "Warning", "Info", "Debug"], style=wx.CB_READONLY)
        self.combo1.SetValue(self.config.get('logging','consoleLoglevel').capitalize())
        self.combo1.SetToolTipString('Determines the minimum loglevel a logmessage must have to be printed to the console.')
        loggingItems.Add(self.combo1, 1)

        #up speed        
        label2a = wx.StaticText(self, -1, "File loglevel:")
        label2a.SetToolTipString('Determines the minimum loglevel a logmessage must have to be written to the logfile.')
        loggingItems.Add(label2a, 1, wx.EXPAND | wx.ALIGN_CENTER_VERTICAL)
        
        self.combo2 = wx.ComboBox(self, -1, size = wx.Size(85, -1),\
                                  choices=["Critical", "Error", "Warning", "Info", "Debug"], style=wx.CB_READONLY)
        self.combo2.SetValue(self.config.get('logging','fileLoglevel').capitalize())
        self.combo2.SetToolTipString('Determines the minimum loglevel a logmessage must have to be written to the logfile.')
        loggingItems.Add(self.combo2, 1)
        
        loggingItems.AddGrowableCol(0, 1)
        
        #build up comment box 
        commentLabel = wx.StaticText(self, -1, 'It is probably best to use "Error" or "Warning" for normal operation, '+\
                                               '"Critical" if you want to minimise logging to very serious errors. '+\
                                               '"Info" is only something for the curious and "Debug" for developers or the insane. ;)\n\n'+\
                                               'Warning: Setting the logfile to "Debug" will create GBs of logs per day, '+\
                                               'setting the console loglevel to that level will affect performance drastically!')
        commentBoxSizer.Add(commentLabel, 1, flag = wx.EXPAND | wx.ALL, border = 5)

        #build up network box
        loggingBoxItems.Add(loggingItems, 1, wx.EXPAND | wx.ALL, border = 5)
        loggingBoxItems.Add(commentBoxSizer, 1, wx.EXPAND | wx.ALL, border = 0)
        loggingBoxItems.AddGrowableCol(0, 1)
        loggingBoxItems.AddGrowableRow(1, 1)
        loggingBoxSizer.Add(loggingBoxItems, 1, wx.EXPAND | wx.ALL, border = 0)

        vBox.Add(loggingBoxSizer, 1, wx.EXPAND | wx.ALL, border = 2)
        #Line everythign up
        self.SetSizer(vBox)
        self.Layout()
        

    def saveConfig(self, optionDict):
        optionDict[('logging','consoleLoglevel')] = str(self.combo1.GetValue().lower())
        optionDict[('logging','fileLoglevel')] = str(self.combo2.GetValue().lower())
        



class Network_ConfigPanel(wx.Panel):
    def __init__(self, config, parent, **kwargs):
        wx.Panel.__init__(self, parent, **kwargs)
        self.config = config
        #stuff
        vBox = wx.BoxSizer(wx.VERTICAL)

        #build up boxes
        networkBox = wx.StaticBox(self, -1, "Network")
        networkBoxSizer = wx.StaticBoxSizer(networkBox, wx.VERTICAL)
        networkBoxItems = wx.FlexGridSizer(cols = 1, vgap = 3, hgap = 5)

        commentBox = wx.StaticBox(self, -1, "Note")
        commentBoxSizer = wx.StaticBoxSizer(commentBox, wx.VERTICAL)

        #build speedLimiter box        
        limiterItems = wx.FlexGridSizer(cols = 2, vgap = 3, hgap = 5)
        
        #down speed        
        label1a = wx.StaticText(self, -1, "max Download speed (KB/s):")
        label1a.SetToolTipString('Restricts the client to not download more kilobytes per second then set here')
        limiterItems.Add(label1a, 1, wx.ALIGN_CENTER_VERTICAL | wx.EXPAND)
        
        self.spin1 = wx.SpinCtrl(self, -1, size=wx.Size(80,-1))
        self.spin1.SetRange(1, 1048576)
        self.spin1.SetValue(self.config.getInt('network','downSpeedLimit')/1024)
        self.spin1.SetToolTipString('Restricts the client to not download more kilobytes per second then set here')
        limiterItems.Add(self.spin1, 1)

        #up speed        
        label2a = wx.StaticText(self, -1, "max Upload speed (KB/s):")
        label2a.SetToolTipString('Restricts the client to not upload more kilobytes per second then set here')
        limiterItems.Add(label2a, 1, wx.ALIGN_CENTER_VERTICAL | wx.EXPAND)
        
        self.spin2 = wx.SpinCtrl(self, -1, size=wx.Size(80,-1))
        self.spin2.SetRange(1, 1048576)
        self.spin2.SetValue(self.config.getInt('network','upSpeedLimit')/1024)
        self.spin2.SetToolTipString('Restricts the client to not upload more kilobytes per second then set here')
        limiterItems.Add(self.spin2, 1)
        
        limiterItems.AddGrowableCol(0, 1)
        
        #build up comment box 
        commentLabel = wx.StaticText(self, -1, "Especially the upload limit is more of an average limit because of "+\
                                               "both buffers in this clients sam library and i2p itself.")
        commentBoxSizer.Add(commentLabel, 1, flag = wx.EXPAND | wx.ALL, border = 5)

        #build up network box
        networkBoxItems.Add(limiterItems, 1, wx.EXPAND | wx.ALL, border = 5)
        networkBoxItems.Add(commentBoxSizer, 1, wx.EXPAND | wx.ALL, border = 0)
        networkBoxItems.AddGrowableCol(0, 1)
        networkBoxItems.AddGrowableRow(1, 1)
        networkBoxSizer.Add(networkBoxItems, 1, wx.EXPAND | wx.ALL, border = 0)

        vBox.Add(networkBoxSizer, 1, wx.EXPAND | wx.ALL, border = 2)
        #Line everythign up
        self.SetSizer(vBox)
        self.Layout()
        

    def saveConfig(self, optionDict):
        optionDict[('network','downSpeedLimit')] = self.spin1.GetValue()*1024
        optionDict[('network','upSpeedLimit')] = self.spin2.GetValue()*1024
        
        
        

class Http_ConfigPanel(wx.Panel):
    def __init__(self, config, parent, **kwargs):
        wx.Panel.__init__(self, parent, **kwargs)
        self.config = config
        #stuff
        vBox = wx.BoxSizer(wx.VERTICAL)

        ##build up main box and sizers
        httpBox = wx.StaticBox(self, -1, "HTTP")
        httpBoxSizer = wx.StaticBoxSizer(httpBox, wx.VERTICAL)
        httpBoxItems = wx.FlexGridSizer(cols = 1, vgap = 10, hgap = 5)


        ##torrent fetch options
        torrentFetchBox = wx.StaticBox(self, -1, "Torrent fetches")
        torrentFetchBoxSizer = wx.StaticBoxSizer(torrentFetchBox, wx.VERTICAL)
        torrentFetchBoxItems = wx.FlexGridSizer(cols = 2, vgap = 3, hgap = 5)
        torrentFetchBoxItems.AddGrowableCol(0, 1)
            
        #retry interval
        label = wx.StaticText(self, -1, "Retry interval (seconds):")
        label.SetToolTipString('Waittime before retrying when a fetch fails')
        torrentFetchBoxItems.Add(label, 1, wx.ALIGN_CENTER_VERTICAL | wx.EXPAND)
        
        self.spin1 = wx.SpinCtrl(self, -1, size=wx.Size(115,-1))
        self.spin1.SetRange(60, 3600)
        self.spin1.SetValue(self.config.get('http','torrentFetchRetryInterval'))
        self.spin1.SetToolTipString('Waittime before retrying when a fetch fails')
        torrentFetchBoxItems.Add(self.spin1, 1)
        
        #transfer timeout
        label = wx.StaticText(self, -1, "Transfer timeout (seconds):")
        label.SetToolTipString('Maximum waittime between receiving data before the request is timed out')
        torrentFetchBoxItems.Add(label, 1, wx.ALIGN_CENTER_VERTICAL | wx.EXPAND)
        
        self.spin2 = wx.SpinCtrl(self, -1, size=wx.Size(115,-1))
        self.spin2.SetRange(60, 3600)
        self.spin2.SetValue(self.config.get('http','torrentFetchTransferTimeout'))
        self.spin2.SetToolTipString('Maximum waittime between receiving data before the request is timed out')
        torrentFetchBoxItems.Add(self.spin2, 1)
        
        #request timeout
        label = wx.StaticText(self, -1, "Request timeout (seconds):")
        label.SetToolTipString('Maximum total time until a request is timed out')
        torrentFetchBoxItems.Add(label, 1, wx.ALIGN_CENTER_VERTICAL | wx.EXPAND)
        
        self.spin3 = wx.SpinCtrl(self, -1, size=wx.Size(115,-1))
        self.spin3.SetRange(60, 3600)
        self.spin3.SetValue(self.config.get('http','torrentFetchRequestTimeout'))
        self.spin3.SetToolTipString('Maximum total time until a request is timed out')
        torrentFetchBoxItems.Add(self.spin3, 1)
        
        #max header size
        label = wx.StaticText(self, -1, "Max header size (KB):")
        label.SetToolTipString('Maximum allowed size of the http header')
        torrentFetchBoxItems.Add(label, 1, wx.ALIGN_CENTER_VERTICAL | wx.EXPAND)
        
        self.spin4 = wx.SpinCtrl(self, -1, size=wx.Size(115,-1))
        self.spin4.SetRange(1, 128)
        self.spin4.SetValue(self.config.get('http','torrentFetchMaxHeaderSize')/1024)
        self.spin4.SetToolTipString('Maximum allowed size of the http header')
        torrentFetchBoxItems.Add(self.spin4, 1)
        
        #max header size
        label = wx.StaticText(self, -1, "Max data size (KB):")
        label.SetToolTipString('Maximum allowed size of the data part of the http request')
        torrentFetchBoxItems.Add(label, 1, wx.ALIGN_CENTER_VERTICAL | wx.EXPAND)
        
        self.spin5 = wx.SpinCtrl(self, -1, size=wx.Size(115,-1))
        self.spin5.SetRange(128, 1048576)
        self.spin5.SetValue(self.config.get('http','torrentFetchMaxDataSize')/1024)
        self.spin5.SetToolTipString('Maximum allowed size of the data part of the http request')
        torrentFetchBoxItems.Add(self.spin5, 1)
        
        #add item sizer to box sizer
        torrentFetchBoxSizer.Add(torrentFetchBoxItems, 1, wx.EXPAND | wx.ALL, border = 5)
        
        
        ##tracker request options
        trackerRequestBox = wx.StaticBox(self, -1, "Tracker requests")
        trackerRequestBoxSizer = wx.StaticBoxSizer(trackerRequestBox, wx.VERTICAL)
        trackerRequestBoxItems = wx.FlexGridSizer(cols = 2, vgap = 3, hgap = 5)
        trackerRequestBoxItems.AddGrowableCol(0, 1)
        
        #transfer timeout
        label = wx.StaticText(self, -1, "Transfer timeout (seconds):")
        label.SetToolTipString('Maximum waittime between receiving data before the request is timed out')
        trackerRequestBoxItems.Add(label, 1, wx.ALIGN_CENTER_VERTICAL | wx.EXPAND)
        
        self.spin6 = wx.SpinCtrl(self, -1, size=wx.Size(115,-1))
        self.spin6.SetRange(60, 3600)
        self.spin6.SetValue(self.config.get('http','trackerRequestTransferTimeout'))
        self.spin6.SetToolTipString('Maximum waittime between receiving data before the request is timed out')
        trackerRequestBoxItems.Add(self.spin6, 1)
        
        #request timeout
        label = wx.StaticText(self, -1, "Request timeout (seconds):")
        label.SetToolTipString('Maximum total time until a request is timed out')
        trackerRequestBoxItems.Add(label, 1, wx.ALIGN_CENTER_VERTICAL | wx.EXPAND)
        
        self.spin7 = wx.SpinCtrl(self, -1, size=wx.Size(115,-1))
        self.spin7.SetRange(60, 3600)
        self.spin7.SetValue(self.config.get('http','trackerRequestTimeout'))
        self.spin7.SetToolTipString('Maximum total time until a request is timed out')
        trackerRequestBoxItems.Add(self.spin7, 1)
        
        #max header size
        label = wx.StaticText(self, -1, "Max header size (KB):")
        label.SetToolTipString('Maximum allowed size of the http header')
        trackerRequestBoxItems.Add(label, 1, wx.ALIGN_CENTER_VERTICAL | wx.EXPAND)
        
        self.spin8 = wx.SpinCtrl(self, -1, size=wx.Size(115,-1))
        self.spin8.SetRange(1, 128)
        self.spin8.SetValue(self.config.get('http','trackerRequestMaxHeaderSize')/1024)
        self.spin8.SetToolTipString('Maximum allowed size of the http header')
        trackerRequestBoxItems.Add(self.spin8, 1)
        
        #max header size
        label = wx.StaticText(self, -1, "Max data size (KB):")
        label.SetToolTipString('Maximum allowed size of the data part of the http request')
        trackerRequestBoxItems.Add(label, 1, wx.ALIGN_CENTER_VERTICAL | wx.EXPAND)
        
        self.spin9 = wx.SpinCtrl(self, -1, size=wx.Size(115,-1))
        self.spin9.SetRange(128, 1048576)
        self.spin9.SetValue(self.config.get('http','trackerRequestMaxDataSize')/1024)
        self.spin9.SetToolTipString('Maximum allowed size of the data part of the http request')
        trackerRequestBoxItems.Add(self.spin9, 1)
        
        #add item sizer to box sizer
        trackerRequestBoxSizer.Add(trackerRequestBoxItems, 1, wx.EXPAND | wx.ALL, border = 5)
        
        
        ##build up comment box 
        commentBox = wx.StaticBox(self, -1, "Note")
        commentBoxSizer = wx.StaticBoxSizer(commentBox, wx.VERTICAL)
        commentLabel = wx.StaticText(self, -1, 'Request timeouts are not changed for already running requests, so'+\
                                               ' keep that in mind before configuring very long timeouts,\n'+\
                                               'The same applies to the request interval.')
        commentBoxSizer.Add(commentLabel, 1, flag = wx.EXPAND | wx.ALL, border = 5)


        ##build up i2p box
        httpBoxItems.Add(torrentFetchBoxSizer, 1, wx.EXPAND | wx.ALL, border = 0)
        httpBoxItems.Add(trackerRequestBoxSizer, 1, wx.EXPAND | wx.ALL, border = 0)
        httpBoxItems.Add(commentBoxSizer, 1, wx.EXPAND | wx.ALL, border = 0)
        httpBoxItems.AddGrowableCol(0, 1)
        httpBoxItems.AddGrowableRow(2, 1)
        httpBoxSizer.Add(httpBoxItems, 1, wx.EXPAND | wx.ALL, border = 0)


        ##line everything up
        vBox.Add(httpBoxSizer, 1, wx.EXPAND | wx.ALL, border = 2)
        self.SetSizer(vBox)
        self.Layout()
        

    def saveConfig(self, optionDict):
        optionDict[('http', 'torrentFetchRetryInterval')] = self.spin1.GetValue()
        optionDict[('http', 'torrentFetchTransferTimeout')] = self.spin2.GetValue()
        optionDict[('http', 'torrentFetchRequestTimeout')] = self.spin3.GetValue()
        optionDict[('http', 'torrentFetchMaxHeaderSize')] = self.spin4.GetValue() * 1024
        optionDict[('http', 'torrentFetchMaxDataSize')] = self.spin5.GetValue() * 1024
        optionDict[('http', 'trackerRequestTransferTimeout')] = self.spin6.GetValue()
        optionDict[('http', 'trackerRequestTimeout')] = self.spin7.GetValue()
        optionDict[('http', 'trackerRequestMaxHeaderSize')] = self.spin8.GetValue() * 1024
        optionDict[('http', 'trackerRequestMaxDataSize')] = self.spin9.GetValue() * 1024
        
        
        
        
class I2P_ConfigPanel(wx.Panel):
    def __init__(self, config, parent, **kwargs):
        wx.Panel.__init__(self, parent, **kwargs)
        self.config = config
        #stuff
        vBox = wx.BoxSizer(wx.VERTICAL)

        ##build up main box and sizers
        i2pBox = wx.StaticBox(self, -1, "I2P")
        i2pBoxSizer = wx.StaticBoxSizer(i2pBox, wx.VERTICAL)
        i2pBoxItems = wx.FlexGridSizer(cols = 1, vgap = 10, hgap = 5)


        ##sam options
        samOptionBox = wx.StaticBox(self, -1, "Sam")
        samOptionBoxSizer = wx.StaticBoxSizer(samOptionBox, wx.VERTICAL)
        samOptionBoxItems = wx.FlexGridSizer(cols = 2, vgap = 3, hgap = 5)
        samOptionBoxItems.AddGrowableCol(0, 1)
            
        #ip of sam bridge
        label1a = wx.StaticText(self, -1, "Sam IP:")
        label1a.SetToolTipString('Enter the IP address of the Sam bridge here')
        samOptionBoxItems.Add(label1a, 1, wx.ALIGN_CENTER_VERTICAL | wx.EXPAND)
        
        self.ipField1 = IpAddrCtrl(self, -1)
        self.ipField1.SetValue(self.config.get('i2p','samIp'))
        self.ipField1.SetToolTipString('Enter the IP address of the Sam bridge here')
        samOptionBoxItems.Add(self.ipField1, 1)
        
        
        #port of sam bridge
        label2a = wx.StaticText(self, -1, "Sam port:")
        label2a.SetToolTipString('Enter the port of the Sam bridge here')
        samOptionBoxItems.Add(label2a, 1, wx.ALIGN_CENTER_VERTICAL | wx.EXPAND)
        
        self.spin1 = wx.SpinCtrl(self, -1, size=wx.Size(115,-1))
        self.spin1.SetRange(1, 65535)
        self.spin1.SetValue(self.config.getInt('i2p','samPort'))
        self.spin1.SetToolTipString('Enter the port of the Sam bridge here')
        samOptionBoxItems.Add(self.spin1, 1)
        
        
        #sam display name
        label3a = wx.StaticText(self, -1, "Display name:")
        label3a.SetToolTipString('This name will appear in the destinations overview of the i2p router webinterface.')
        samOptionBoxItems.Add(label3a, 1, wx.ALIGN_CENTER_VERTICAL | wx.EXPAND)
        
        self.edit1 = wx.TextCtrl(self, -1, "", size=wx.Size(115,-1))
        self.edit1.SetValue(self.config.get('i2p','samDisplayName'))        
        self.edit1.SetToolTipString('This name will appear in the destinations overview of the i2p router webinterface.')
        samOptionBoxItems.Add(self.edit1, 1)
        
        
        #sam session name
        label4a = wx.StaticText(self, -1, "Session name:")
        label4a.SetToolTipString('This name will be used by the sam bridge to determine which i2p destination should be used for this client, changing it will also change the used destination.')
        samOptionBoxItems.Add(label4a, 1, wx.ALIGN_CENTER_VERTICAL | wx.EXPAND)
        
        self.edit2 = wx.TextCtrl(self, -1, "", size=wx.Size(115,-1))
        self.edit2.SetValue(self.config.get('i2p','samSessionName'))        
        self.edit2.SetToolTipString('This name will be used by the sam bridge to determine which i2p destination should be used for this client, changing it will also change the used destination.')
        samOptionBoxItems.Add(self.edit2, 1)
        
        
        #add item sizer to box sizer
        samOptionBoxSizer.Add(samOptionBoxItems, 1, wx.EXPAND | wx.ALL, border = 5)
        
        
        ##tunnel options
        tunnelOptionBox = wx.StaticBox(self, -1, "Tunnel options")
        tunnelOptionBoxSizer = wx.StaticBoxSizer(tunnelOptionBox, wx.VERTICAL)
        tunnelOptionBoxItems = wx.FlexGridSizer(cols = 3, vgap = 3, hgap = 20)
        
        #headline
        label5a = wx.StaticText(self, -1, "")
        tunnelOptionBoxItems.Add(label5a, 1)
        label5b = wx.StaticText(self, -1, "In")
        tunnelOptionBoxItems.Add(label5b, 1)
        label5c = wx.StaticText(self, -1, "Out")
        tunnelOptionBoxItems.Add(label5c, 1)
        
        
        #ZeroHops
        label6a = wx.StaticText(self, -1, "Zero Hops:")
        label6a.SetToolTipString('Allow Zero Hops?')
        tunnelOptionBoxItems.Add(label6a, 1, wx.ALIGN_CENTER_VERTICAL | wx.EXPAND)
        
        self.check1In = wx.CheckBox(self, -1)
        self.check1In.SetToolTipString('Allow Zero Hops for inbound tunnels?')
        self.check1In.SetValue(self.config.getBool('i2p','samZeroHopsIn'))
        tunnelOptionBoxItems.Add(self.check1In, 1)
        
        self.check1Out = wx.CheckBox(self, -1)
        self.check1Out.SetToolTipString('Allow Zero Hops for outbound tunnels?')
        self.check1Out.SetValue(self.config.getBool('i2p','samZeroHopsOut'))
        tunnelOptionBoxItems.Add(self.check1Out, 1)
        
        
        #tunnel quantity
        label7a = wx.StaticText(self, -1, "Number of tunnels:")
        label7a.SetToolTipString('Number of tunnels')
        tunnelOptionBoxItems.Add(label7a, 1, wx.ALIGN_CENTER_VERTICAL | wx.EXPAND)
        
        self.spin2In = wx.SpinCtrl(self, -1, size=wx.Size(80,-1))
        self.spin2In.SetRange(1, 5)
        self.spin2In.SetValue(self.config.getInt('i2p','samNumOfTunnelsIn'))
        self.spin2In.SetToolTipString('Number of inbound tunnels')
        tunnelOptionBoxItems.Add(self.spin2In, 1)
        
        self.spin2Out = wx.SpinCtrl(self, -1, size=wx.Size(80,-1))
        self.spin2Out.SetRange(1, 5)
        self.spin2Out.SetValue(self.config.getInt('i2p','samNumOfTunnelsOut'))
        self.spin2Out.SetToolTipString('Number of outbound tunnels')
        tunnelOptionBoxItems.Add(self.spin2Out, 1)
        
        
        #backup tunnel quantity
        label8a = wx.StaticText(self, -1, "Number of backup tunnels:")
        label8a.SetToolTipString('Number of backup tunnels')
        tunnelOptionBoxItems.Add(label8a, 1, wx.ALIGN_CENTER_VERTICAL | wx.EXPAND)
        
        self.spin3In = wx.SpinCtrl(self, -1, size=wx.Size(80,-1))
        self.spin3In.SetRange(0, 2)
        self.spin3In.SetValue(self.config.getInt('i2p','samNumOfBackupTunnelsIn'))
        self.spin3In.SetToolTipString('Number of inbound backup tunnels')
        tunnelOptionBoxItems.Add(self.spin3In, 1)
        
        self.spin3Out = wx.SpinCtrl(self, -1, size=wx.Size(80,-1))
        self.spin3Out.SetRange(0, 2)
        self.spin3Out.SetValue(self.config.getInt('i2p','samNumOfBackupTunnelsOut'))
        self.spin3Out.SetToolTipString('Number of outbound backup tunnels')
        tunnelOptionBoxItems.Add(self.spin3Out, 1)
        
        
        #tunnel length
        label9a = wx.StaticText(self, -1, "Length of tunnels:")
        label9a.SetToolTipString('Length of tunnels')
        tunnelOptionBoxItems.Add(label9a, 1, wx.ALIGN_CENTER_VERTICAL | wx.EXPAND)
        
        self.spin4In = wx.SpinCtrl(self, -1, size=wx.Size(80,-1))
        self.spin4In.SetRange(0, 3)
        self.spin4In.SetValue(self.config.getInt('i2p','samTunnelLengthIn'))
        self.spin4In.SetToolTipString('Length of inbound tunnels')
        tunnelOptionBoxItems.Add(self.spin4In, 1)
        
        self.spin4Out = wx.SpinCtrl(self, -1, size=wx.Size(80,-1))
        self.spin4Out.SetRange(0, 3)
        self.spin4Out.SetValue(self.config.getInt('i2p','samTunnelLengthOut'))
        self.spin4Out.SetToolTipString('Length of outbound tunnels')
        tunnelOptionBoxItems.Add(self.spin4Out, 1)
        
        
        #tunnel length variance
        label10a = wx.StaticText(self, -1, "Variance of tunnel length:")
        label10a.SetToolTipString('Controls how much the length of the tunnels is randomly changed. If negative, the tunnel length varies +/- the set value, else only + the set value.')
        tunnelOptionBoxItems.Add(label10a, 1, wx.ALIGN_CENTER_VERTICAL | wx.EXPAND)
        
        self.spin8In = wx.SpinCtrl(self, -1, size=wx.Size(80,-1))
        self.spin8In.SetRange(-2, 2)
        self.spin8In.SetValue(self.config.getInt('i2p','samTunnelLengthVarianceIn'))
        self.spin8In.SetToolTipString('Controls how much the length of the inbound tunnels is randomly changed. If negative, the tunnel length varies +/- the set value, else only + the set value.')
        tunnelOptionBoxItems.Add(self.spin8In, 1)
        
        self.spin8Out = wx.SpinCtrl(self, -1, size=wx.Size(80,-1))
        self.spin8Out.SetRange(-2, 2)
        self.spin8Out.SetValue(self.config.getInt('i2p','samTunnelLengthVarianceOut'))
        self.spin8Out.SetToolTipString('Controls how much the length of the outbound tunnels is randomly changed. If negative, the tunnel length varies +/- the set value, else only + the set value.')
        tunnelOptionBoxItems.Add(self.spin8Out, 1)
        
        
        #add item sizer to box sizer
        tunnelOptionBoxSizer.Add(tunnelOptionBoxItems, 1, wx.EXPAND | wx.ALL, border = 5)
        
        
        ##build up comment box 
        commentBox = wx.StaticBox(self, -1, "Note")
        commentBoxSizer = wx.StaticBoxSizer(commentBox, wx.VERTICAL)
        commentLabel = wx.StaticText(self, -1, 'Changing any of these settings will force a reconnect to the i2p router, closing all existing connections to other clients.\n\n'+\
                                               'Both the display and session name must be unique for the used i2p router. If "TRANSIENT" (without the quotes) is used as a session name, the client will get a different i2p destination after each reconnect to the i2p router.\n\n'+\
                                               'Be careful with changing the tunnel options. These are not only relevant for performance but also for anonymity!')
        commentBoxSizer.Add(commentLabel, 1, flag = wx.EXPAND | wx.ALL, border = 5)


        ##build up i2p box
        i2pBoxItems.Add(samOptionBoxSizer, 1, wx.EXPAND | wx.ALL, border = 0)
        i2pBoxItems.Add(tunnelOptionBoxSizer, 1, wx.EXPAND | wx.ALL, border = 0)
        i2pBoxItems.Add(commentBoxSizer, 1, wx.EXPAND | wx.ALL, border = 0)
        i2pBoxItems.AddGrowableCol(0, 1)
        i2pBoxItems.AddGrowableRow(2, 1)
        i2pBoxSizer.Add(i2pBoxItems, 1, wx.EXPAND | wx.ALL, border = 0)


        ##line everything up
        vBox.Add(i2pBoxSizer, 1, wx.EXPAND | wx.ALL, border = 2)
        self.SetSizer(vBox)
        self.Layout()
        

    def saveConfig(self, optionDict):
        optionDict[('i2p', 'samIp')] = self.ipField1.GetValue().replace(' ', '')
        optionDict[('i2p', 'samPort')] = self.spin1.GetValue()
        optionDict[('i2p', 'samDisplayName')] = self.edit1.GetValue().replace(' ', '').encode('UTF-8')
        optionDict[('i2p', 'samSessionName')] = self.edit2.GetValue().replace(' ', '').encode('UTF-8')
        optionDict[('i2p', 'samZeroHopsIn')] = self.check1In.GetValue()
        optionDict[('i2p', 'samZeroHopsOut')] = self.check1Out.GetValue()
        optionDict[('i2p', 'samNumOfTunnelsIn')] = self.spin2In.GetValue()
        optionDict[('i2p', 'samNumOfTunnelsOut')] = self.spin2Out.GetValue()
        optionDict[('i2p', 'samNumOfBackupTunnelsIn')] = self.spin3In.GetValue()
        optionDict[('i2p', 'samNumOfBackupTunnelsOut')] = self.spin3Out.GetValue()
        optionDict[('i2p', 'samTunnelLengthIn')] = self.spin4In.GetValue()
        optionDict[('i2p', 'samTunnelLengthOut')] = self.spin4Out.GetValue()
        optionDict[('i2p', 'samTunnelLengthVarianceIn')] = self.spin8In.GetValue()
        optionDict[('i2p', 'samTunnelLengthVarianceOut')] = self.spin8Out.GetValue()
        
        


class Paths_ConfigPanel(wx.Panel):
    def __init__(self, config, parent, **kwargs):
        wx.Panel.__init__(self, parent, **kwargs)
        self.config = config
        #stuff
        vBox = wx.BoxSizer(wx.VERTICAL)

        #build up boxes
        pathsBox = wx.StaticBox(self, -1, "Torrents")
        pathsSizer = wx.StaticBoxSizer(pathsBox, wx.VERTICAL)
        pathsItems = wx.FlexGridSizer(cols = 1, vgap = 3, hgap = 0)

        commentBox = wx.StaticBox(self, -1, "Note")
        commentSizer = wx.StaticBoxSizer(commentBox, wx.VERTICAL)

        #build paths box        
        pathsRealItems = wx.FlexGridSizer(cols = 3, vgap = 3, hgap = 5)
        
        #torrent path        
        label2 = wx.StaticText(self, -1, "Torrent Folder:")
        label2.SetToolTipString('This directory is used as a default for any torrent open dialog.')
        pathsRealItems.Add(label2, 1, wx.ALIGN_CENTER_VERTICAL)

        self.edit1 = wx.TextCtrl(self, -1, "")
        self.edit1.SetValue(self.config.get('paths','torrentFolder'))        
        self.edit1.SetToolTipString('This directory is used as a default for any torrent open dialog.')
        pathsRealItems.Add(self.edit1, 1, wx.EXPAND)

        buttonId1 = wx.NewId()
        self.button1 = wx.Button(self, buttonId1, "...", size=(25,-1))
        pathsRealItems.Add(self.button1, 1)
        wx.EVT_BUTTON(self, buttonId1, self.OnButton1)

        #download Path
        label3 = wx.StaticText(self, -1, "Downloads Folder:")
        label3.SetToolTipString('This directory is used as a default for any save-to dialog.')
        pathsRealItems.Add(label3, 1, wx.ALIGN_CENTER_VERTICAL)
        
        self.edit2 = wx.TextCtrl(self, -1, "")
        self.edit2.SetValue(self.config.get('paths','downloadFolder'))        
        self.edit2.SetToolTipString('This directory is used as a default for any save-to dialog.')
        pathsRealItems.Add(self.edit2, 1, wx.EXPAND)

        buttonId2 = wx.NewId()
        self.button2 = wx.Button(self, buttonId2, "...", size=(25,-1))
        pathsRealItems.Add(self.button2, 1)
        wx.EVT_BUTTON(self, buttonId2, self.OnButton2)
        
        pathsRealItems.AddGrowableCol(1, 1)
        
        #build up comment box 
        commentLabel = wx.StaticText(self, -1, 'These paths only matter for the "choose file/directory" dialogs')
        commentSizer.Add(commentLabel, 1, flag = wx.EXPAND | wx.ALL, border = 5)

        #build up paths box
        pathsItems.Add(pathsRealItems, 1, wx.EXPAND | wx.ALL, border = 5)
        pathsItems.Add(commentSizer, 1, wx.EXPAND | wx.ALL, border = 0)
        pathsItems.AddGrowableCol(0, 1)
        pathsItems.AddGrowableRow(1, 1)
        pathsSizer.Add(pathsItems, 1, wx.EXPAND | wx.ALL, border = 0)

        vBox.Add(pathsSizer, 1, wx.EXPAND | wx.ALL, border = 2)
        #Line everythign up
        self.SetSizer(vBox)
        self.Layout()
        

    def OnButton1(self, event):
        selectedPath = self.getPath(self.edit1.GetValue())
        if selectedPath is not None:
            self.edit1.SetValue(selectedPath)
            

    def OnButton2(self, event):
        selectedPath = self.getPath(self.edit2.GetValue())
        if selectedPath is not None:
            self.edit2.SetValue(selectedPath)
            

    def getPath(self, defaultPath):
        path = None
        pathDlg = wx.DirDialog(self, "Choose a directory:", defaultPath=defaultPath, style=wx.DD_DEFAULT_STYLE|wx.DD_NEW_DIR_BUTTON)
        if pathDlg.ShowModal() == wx.ID_OK:
            path = os.path.normpath(pathDlg.GetPath())
        pathDlg.Destroy()
        return path
    

    def saveConfig(self, optionDict):
        optionDict[('paths','torrentFolder')] = self.edit1.GetValue()
        optionDict[('paths','downloadFolder')] = self.edit2.GetValue()
        
 


class Requester_ConfigPanel(wx.Panel):
    def __init__(self, config, parent, **kwargs):
        wx.Panel.__init__(self, parent, **kwargs)
        self.config = config
        #stuff
        vBox = wx.BoxSizer(wx.VERTICAL)

        #build up boxes
        requesterBox = wx.StaticBox(self, -1, "Requester")
        requesterBoxSizer = wx.StaticBoxSizer(requesterBox, wx.VERTICAL)
        requesterBoxItems = wx.FlexGridSizer(cols = 1, vgap = 3, hgap = 5)

        commentBox = wx.StaticBox(self, -1, "Note")
        commentBoxSizer = wx.StaticBoxSizer(commentBox, wx.VERTICAL)
        
        #build requester box        
        requesterRealItems = wx.FlexGridSizer(cols = 2, vgap = 3, hgap = 5)

        #prio
        label1 = wx.StaticText(self, -1, "Always prioritise by availability:")
        label1.SetToolTipString('Always prioritise pieces by their availability, regardless of in progress pieces?')
        requesterRealItems.Add(label1, 1, wx.ALIGN_CENTER_VERTICAL)
        
        self.check1 = wx.CheckBox(self, -1)
        self.check1.SetToolTipString('Always prioritise pieces by their availability, regardless of in progress pieces?')
        self.check1.SetValue(self.config.getBool('requester','strictAvailabilityPrio'))
        requesterRealItems.Add(self.check1, 1)
        
        #build up comment box 
        commentLabel = wx.StaticText(self, -1, "Prioritising pieces by their availability and rather starting to request "+\
                                               "rare new pieces instead of further requesting less rare in-progress pieces "+\
                                               "is prefferable long term.\n"+\
                                               "Only disable it if you want to minimalise resource "+\
                                               "usage as far as possible (the gain is minimal) and/or only run PyBit for one "+\
                                               "or two hours at once.")
        commentBoxSizer.Add(commentLabel, 1, flag = wx.EXPAND | wx.ALL, border = 5)

        #build up requester box
        requesterBoxItems.Add(requesterRealItems, 1, wx.EXPAND | wx.ALL, border = 5)
        requesterBoxItems.Add(commentBoxSizer, 1, wx.EXPAND | wx.ALL, border = 0)
        requesterBoxItems.AddGrowableCol(0, 1)
        requesterBoxItems.AddGrowableRow(1, 1)
        requesterBoxSizer.Add(requesterBoxItems, 1, wx.EXPAND | wx.ALL, border = 0)

        vBox.Add(requesterBoxSizer, 1, wx.EXPAND | wx.ALL, border = 2)
        #Line everythign up
        self.SetSizer(vBox)
        self.Layout()
        

    def saveConfig(self, optionDict):
        optionDict[('requester', 'strictAvailabilityPrio')] = self.check1.GetValue()




class Storage_ConfigPanel(wx.Panel):
    def __init__(self, config, parent, **kwargs):
        wx.Panel.__init__(self, parent, **kwargs)
        self.config = config
        #stuff
        vBox = wx.BoxSizer(wx.VERTICAL)

        #build up boxes
        storageBox = wx.StaticBox(self, -1, "Storage")
        storageBoxSizer = wx.StaticBoxSizer(storageBox, wx.VERTICAL)
        storageBoxItems = wx.FlexGridSizer(cols = 1, vgap = 3, hgap = 5)

        commentBox = wx.StaticBox(self, -1, "Note")
        commentBoxSizer = wx.StaticBoxSizer(commentBox, wx.VERTICAL)
        
        #build storage box        
        storageRealItems = wx.FlexGridSizer(cols = 2, vgap = 3, hgap = 5)

        #skip file checks
        label1 = wx.StaticText(self, -1, "Skip file checks when possible:")
        label1.SetToolTipString('Only check if the files of a torrent exist and have the right size when the torrent is run for the first time?')
        storageRealItems.Add(label1, 1, wx.ALIGN_CENTER_VERTICAL)
        
        self.check1 = wx.CheckBox(self, -1)
        self.check1.SetToolTipString('Only check if the files of a torrent exist and have the right size when the torrent is run for the first time?')
        self.check1.SetValue(self.config.getBool('storage','skipFileCheck'))
        storageRealItems.Add(self.check1, 1)
        
        #store progress info on disk
        label2 = wx.StaticText(self, -1, "Store progress information on disk:")
        label2.SetToolTipString('Store the information, which piece is already downloaded and which not, on disk?')
        storageRealItems.Add(label2, 1, wx.ALIGN_CENTER_VERTICAL)
        
        self.check2 = wx.CheckBox(self, -1)
        self.check2.SetToolTipString('Store the information, which piece is already downloaded and which not, on disk?')
        self.check2.SetValue(self.config.getBool('storage','persistPieceStatus'))
        storageRealItems.Add(self.check2, 1)
        
        #build up comment box 
        commentLabel = wx.StaticText(self, -1, 'Storing progress information on disk is commonly called "fast resume", '+\
                                               'meaning that with the help of the stored information torrents can be '+\
                                               'started near instantly after program restarts, skipping the time and CPU '+\
                                               'consuming hashing which is normally needed.')
                                            
        commentBoxSizer.Add(commentLabel, 1, flag = wx.EXPAND | wx.ALL, border = 5)

        #build up storage box
        storageBoxItems.Add(storageRealItems, 1, wx.EXPAND | wx.ALL, border = 5)
        storageBoxItems.Add(commentBoxSizer, 1, wx.EXPAND | wx.ALL, border = 0)
        storageBoxItems.AddGrowableCol(0, 1)
        storageBoxItems.AddGrowableRow(1, 1)
        storageBoxSizer.Add(storageBoxItems, 1, wx.EXPAND | wx.ALL, border = 0)

        vBox.Add(storageBoxSizer, 1, wx.EXPAND | wx.ALL, border = 2)
        #Line everythign up
        self.SetSizer(vBox)
        self.Layout()
        

    def saveConfig(self, optionDict):
        optionDict[('storage', 'skipFileCheck')] = self.check1.GetValue()
        optionDict[('storage', 'persistPieceStatus')] = self.check2.GetValue()




        
        
        
        
class Tracker_ConfigPanel(wx.Panel):
    def __init__(self, config, parent, **kwargs):
        wx.Panel.__init__(self, parent, **kwargs)
        self.config = config
        #stuff
        vBox = wx.BoxSizer(wx.VERTICAL)

        ##build up main box and sizers
        trackerBox = wx.StaticBox(self, -1, "Tracker")
        trackerBoxSizer = wx.StaticBoxSizer(trackerBox, wx.VERTICAL)
        trackerBoxItems = wx.FlexGridSizer(cols = 1, vgap = 10, hgap = 5)
        
        
        ##announcing
        announceOptionsBox = wx.StaticBox(self, -1, "Announcing")
        announceOptionsBoxSizer = wx.StaticBoxSizer(announceOptionsBox, wx.VERTICAL)
        announceOptionsBoxItems = wx.FlexGridSizer(cols = 2, vgap = 3, hgap = 5)
        announceOptionsBoxItems.AddGrowableCol(0, 1)
        
        #scrape interval
        label = wx.StaticText(self, -1, "Announce interval (minutes):")
        label.SetToolTipString('How often (in minutes) should announcing be done?')
        announceOptionsBoxItems.Add(label, 1, wx.ALIGN_CENTER_VERTICAL | wx.EXPAND)
        
        self.spin1 = wx.SpinCtrl(self, -1, size=wx.Size(85,-1))
        self.spin1.SetRange(30, 120)
        self.spin1.SetValue(self.config.get('tracker','announceInterval')/60)
        self.spin1.SetToolTipString('How often (in minutes) should scraping be done?')
        announceOptionsBoxItems.Add(self.spin1, 1)
        
        #add item sizer to box sizer
        announceOptionsBoxSizer.Add(announceOptionsBoxItems, 1, wx.EXPAND | wx.ALL, border = 5)
        
        
        ##scraping
        scrapeOptionsBox = wx.StaticBox(self, -1, "Scraping")
        scrapeOptionsBoxSizer = wx.StaticBoxSizer(scrapeOptionsBox, wx.VERTICAL)
        scrapeOptionsBoxItems = wx.FlexGridSizer(cols = 2, vgap = 3, hgap = 5)
        scrapeOptionsBoxItems.AddGrowableCol(0, 1)
        
        #scrape interval
        label = wx.StaticText(self, -1, "Scrape interval (minutes):")
        label.SetToolTipString('How often (in minutes) should scraping be done?')
        scrapeOptionsBoxItems.Add(label, 1, wx.ALIGN_CENTER_VERTICAL | wx.EXPAND)
        
        self.spin2 = wx.SpinCtrl(self, -1, size=wx.Size(85,-1))
        self.spin2.SetRange(30, 1440)
        self.spin2.SetValue(self.config.get('tracker','scrapeInterval')/60)
        self.spin2.SetToolTipString('How often (in minutes) should scraping be done?')
        scrapeOptionsBoxItems.Add(self.spin2, 1)
            
        #scrape trackers
        label = wx.StaticText(self, -1, "Scrape trackers:")
        label.SetToolTipString('Determines which trackers should be scraped: None, Active (=the tracker used for announcing) or All.')
        scrapeOptionsBoxItems.Add(label, 1, wx.EXPAND | wx.ALIGN_CENTER_VERTICAL)
        
        self.combo1 = wx.ComboBox(self, -1, size = wx.Size(85, -1),\
                                  choices=["None", "Active", "All"], style=wx.CB_READONLY)
        self.combo1.SetValue(self.config.get('tracker','scrapeTrackers').capitalize())
        self.combo1.SetToolTipString('Determines which trackers should be scraped: None, Active (=the tracker used for announcing) or All.')
        scrapeOptionsBoxItems.Add(self.combo1, 1)
        wx.EVT_COMBOBOX(self, self.combo1.GetId(), self.OnComboSelect)
        
        #scrape when stopped
        label = wx.StaticText(self, -1, "Scrape when stopped:")
        label.SetToolTipString('Should the trackers of a torrent even get scraped when the torrent is stopped? Only possible if "Scrape trackers" is set to "All".')
        scrapeOptionsBoxItems.Add(label, 1, wx.EXPAND | wx.ALIGN_CENTER_VERTICAL)
        
        self.check1 = wx.CheckBox(self, -1)
        self.check1.SetToolTipString('Should the trackers of a torrent even get scraped when the torrent is stopped? Only possible if "Scrape trackers" is set to "All".')
        self.check1.SetValue(self.config.get('tracker','scrapeWhileStopped'))
        scrapeOptionsBoxItems.Add(self.check1, 1)
        if not self.combo1.GetValue() == u'All':
            self.check1.Disable()
        
        #clear old scrape stats
        label = wx.StaticText(self, -1, "Clear old scrape stats:")
        label.SetToolTipString('Should outdated scrape stats get cleared (when the last scrape failed, scraping gets disabled, ...)?')
        scrapeOptionsBoxItems.Add(label, 1, wx.EXPAND | wx.ALIGN_CENTER_VERTICAL)
        
        self.check2 = wx.CheckBox(self, -1)
        self.check2.SetToolTipString('Should outdated scrape stats get cleared (when the last scrape failed, scraping gets disabled, ...)?')
        self.check2.SetValue(self.config.get('tracker','clearOldScrapeStats'))
        scrapeOptionsBoxItems.Add(self.check2, 1)
        
        #add item sizer to box sizer
        scrapeOptionsBoxSizer.Add(scrapeOptionsBoxItems, 1, wx.EXPAND | wx.ALL, border = 5)
        
        
        ##build up comment box 
        commentBox = wx.StaticBox(self, -1, "Note")
        commentBoxSizer = wx.StaticBoxSizer(commentBox, wx.VERTICAL)
        commentLabel = wx.StaticText(self, -1, 'Announcing is done by doing a http request to a tracker and is both needed for getting '+\
                                               'peers from a tracker and for adding your own i2p address to the tracker (so that other peers '
                                               'may get it).\n'+\
                                               'If you don\'t know exactly what you are doing, don\'t change the announce interval, because '+\
                                               'too frequent or too infrequent announce requests may cause problems with some trackers.\n\n'+\
                                               'Scraping reffers to getting seed/leecher/download stats from a tracker using a seperate '+\
                                               'http request. Since http requests also consume bandwidth (and ressources in general), '+\
                                               'consider longer scrape intervals or scraping less trackers when you have many torrents queued.')
        commentBoxSizer.Add(commentLabel, 1, flag = wx.EXPAND | wx.ALL, border = 5)


        ##build up i2p box
        trackerBoxItems.Add(announceOptionsBoxSizer, 1, wx.EXPAND | wx.ALL, border = 0)
        trackerBoxItems.Add(scrapeOptionsBoxSizer, 1, wx.EXPAND | wx.ALL, border = 0)
        trackerBoxItems.Add(commentBoxSizer, 1, wx.EXPAND | wx.ALL, border = 0)
        trackerBoxItems.AddGrowableCol(0, 1)
        trackerBoxItems.AddGrowableRow(2, 1)
        trackerBoxSizer.Add(trackerBoxItems, 1, wx.EXPAND | wx.ALL, border = 0)


        ##line everything up
        vBox.Add(trackerBoxSizer, 1, wx.EXPAND | wx.ALL, border = 2)
        self.SetSizer(vBox)
        self.Layout()
        
        
    def OnComboSelect(self, event):
        if self.combo1.GetValue() == u'All':
            self.check1.Enable()
        else:
            self.check1.Disable()
        

    def saveConfig(self, optionDict):
        optionDict[('tracker','announceInterval')] = self.spin1.GetValue() * 60
        optionDict[('tracker','scrapeInterval')] = self.spin2.GetValue() * 60
        optionDict[('tracker','clearOldScrapeStats')] = self.check2.GetValue()
        optionDict[('tracker','scrapeWhileStopped')] = self.check1.GetValue()
        optionDict[('tracker','scrapeTrackers')] = str(self.combo1.GetValue().lower())
        



class ConfigDialog(wx.Frame):
    def __init__(self, config, parent, **kwargs):
        wx.Frame.__init__(self, parent, -1, 'Preferences', size=wx.Size(550, 525),\
                          style = wx.DEFAULT_FRAME_STYLE, **kwargs)
        self.CentreOnScreen()
        self.config = config

        self.hBox = wx.BoxSizer(wx.HORIZONTAL)
        self.vBox = wx.BoxSizer(wx.VERTICAL)
        #tree
        treeId = wx.NewId()
        self.tree = wx.TreeCtrl(parent=self, id=treeId, size=wx.Size(150,-1),\
                                style=wx.TR_DEFAULT_STYLE | wx.TR_HIDE_ROOT | wx.TR_HAS_BUTTONS | wx.TR_SINGLE )
        root = self.tree.AddRoot('root')
        n10 = self.tree.AppendItem(root, "Choker")
        n20 = self.tree.AppendItem(root, "Logging")
        n30 = self.tree.AppendItem(root, "Network")
        n31 = self.tree.AppendItem(n30,  "Http")
        n32 = self.tree.AppendItem(n30,  "I2P")
        n40 = self.tree.AppendItem(root, "Paths")
        n50 = self.tree.AppendItem(root, "Requester")
        n60 = self.tree.AppendItem(root, "Storage")
        n70 = self.tree.AppendItem(root, "Tracker")
        
        self.tree.Expand(n10)
        self.tree.Expand(n20)
        self.tree.Expand(n30)
        self.tree.Expand(n31)
        self.tree.Expand(n32)
        self.tree.Expand(n40)
        self.tree.Expand(n50)
        self.tree.Expand(n60)
        self.tree.Expand(n70)
        self.tree.SelectItem(n10)

        self.vBox.Add(self.tree, 1, wx.EXPAND)
        

        #buttons

        buttonId1 = wx.NewId()
        self.button1 = wx.Button(self, buttonId1, "Save")
        self.Bind(wx.EVT_BUTTON, self.OnSave, id=buttonId1)
        self.vBox.Add(self.button1, 0, wx.EXPAND)

        buttonId2 = wx.NewId()
        self.button2 = wx.Button(self, buttonId2, "Cancel")
        self.Bind(wx.EVT_BUTTON, self.OnClose, id=buttonId2)
        self.vBox.Add(self.button2, 0, wx.EXPAND)
        
        self.hBox.Add(self.vBox, 0, wx.EXPAND)

        #config panels
        self.configPanels = {'Choker':Choker_ConfigPanel(self.config, self),
                             'Logging':Logging_ConfigPanel(self.config, self),
                             'Network':Network_ConfigPanel(self.config, self),
                             'Http':Http_ConfigPanel(self.config, self),
                             'I2P':I2P_ConfigPanel(self.config, self),
                             'Paths':Paths_ConfigPanel(self.config, self),
                             'Requester':Requester_ConfigPanel(self.config, self),
                             'Storage':Storage_ConfigPanel(self.config, self),
                             'Tracker':Tracker_ConfigPanel(self.config, self)}
        self.activePanel = 'Choker'
        
        for panelName in self.configPanels.keys():
            if not panelName == self.activePanel:
                self.configPanels[panelName].Hide()
            self.hBox.Add(self.configPanels[panelName], 1, wx.EXPAND)

        #Line everything up
        self.SetSizer(self.hBox)
        self.Layout()
        
        #events
        self.Bind(wx.EVT_TREE_SEL_CHANGED, self.OnTreeSelectChange, id=treeId)
        self.Show()
        

    def OnTreeSelectChange(self, event):
        self.Freeze()
        self.configPanels[self.activePanel].Hide()
        self.activePanel = self.tree.GetItemText(event.GetItem())
        self.configPanels[self.activePanel].Show()
        self.Layout()
        self.Thaw()
        

    def OnSave(self, event):
        optionDict = {}
        for panel in self.configPanels.values():
            panel.saveConfig(optionDict)
        self.config.setMany(optionDict, False)
        self.Destroy()
        

    def OnClose(self, event):
        self.Destroy()
        

if __name__ == "__main__":
    from Config import Config
    
    #config options
    configDefaults = {'choker':{'chokeInterval':(60, 'int'),
                                'randomSlotRatio':(0.1, 'float'),
                                'maxSlots':(10, 'int'),
                                'slotLimitScope':('global', 'str')},
                      'http':{'torrentFetchRetryInterval':(60, 'int'),
                                  'torrentFetchTransferTimeout':(120, 'int'),
                                  'torrentFetchRequestTimeout':(600, 'int'),
                                  'torrentFetchMaxHeaderSize':(4096, 'int'),
                                  'torrentFetchMaxDataSize':(1048576, 'int'),
                                  'trackerRequestTransferTimeout':(120, 'int'),
                                  'trackerRequestTimeout':(300, 'int'),
                                  'trackerRequestMaxHeaderSize':(4096, 'int'),
                                  'trackerRequestMaxDataSize':(1048576, 'int')},
                      'i2p':{'samIp':('127.0.0.1', 'ip'),
                             'samPort':(7656, 'port'),
                             'samDisplayName':('PyBit', 'str'),
                             'samSessionName':('PyBit', 'str'),
                             'samZeroHopsIn':(False, 'bool'),
                             'samZeroHopsOut':(False, 'bool'),
                             'samNumOfTunnelsIn':(2, 'int'),
                             'samNumOfTunnelsOut':(2, 'int'),
                             'samNumOfBackupTunnelsIn':(0, 'int'),
                             'samNumOfBackupTunnelsOut':(0, 'int'),
                             'samTunnelLengthIn':(2, 'int'),
                             'samTunnelLengthOut':(2, 'int'),
                             'samTunnelLengthVarianceIn':(1, 'int'),
                             'samTunnelLengthVarianceOut':(1, 'int')},
                      'logging':{'consoleLoglevel':('critical', 'str'),
                                 'fileLoglevel':('info', 'str')},
                      'network':{'downSpeedLimit':(102400, 'int'),
                                 'upSpeedLimit':(25600, 'int')},
                      'paths':{'torrentFolder':(u'/tmp', 'unicode'),
                               'downloadFolder':(u'/tmp', 'unicode')},
                      'requester':{'strictAvailabilityPrio':(True, 'bool')},
                      'storage':{'persistPieceStatus':(True, 'bool'),
                                 'skipFileCheck':(False, 'bool')},
                      'tracker':{'announceInterval':(3600, 'int'),
                                 'scrapeInterval':(3600, 'int'),
                                 'clearOldScrapeStats':(True, 'bool'),
                                 'scrapeWhileStopped':(False, 'bool'),
                                 'scrapeTrackers':('active', 'str')}}
                                    
    #create config, add bt defaults
    config = Config('config.conf', configDefaults=configDefaults)
    
    #create GUI
    app = wx.App()
    merk = ConfigDialog(config,None)
    app.MainLoop()
