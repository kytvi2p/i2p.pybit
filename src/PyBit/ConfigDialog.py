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
        loggingItems.Add(label1a, 1, wx.EXPAND)
        
        self.combo1 = wx.ComboBox(self, -1, size = wx.Size(85, -1),\
                                  choices=["Critical", "Error", "Warning", "Info", "Debug"], style=wx.CB_READONLY)
        self.combo1.SetValue(self.config.get('logging','consoleLoglevel').capitalize())
        self.combo1.SetToolTipString('Determines the minimum loglevel a logmessage must have to be printed to the console.')
        loggingItems.Add(self.combo1, 1)

        #up speed        
        label2a = wx.StaticText(self, -1, "File loglevel:")
        label2a.SetToolTipString('Determines the minimum loglevel a logmessage must have to be written to the logfile.')
        loggingItems.Add(label2a, 1, wx.EXPAND)
        
        self.combo2 = wx.ComboBox(self, -1, size = wx.Size(85, -1),\
                                  choices=["Critical", "Error", "Warn", "Info", "Debug"], style=wx.CB_READONLY)
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
        optionDict[('logging','consoleLoglevel')] = self.combo1.GetValue().lower()
        optionDict[('logging','fileLoglevel')] = self.combo2.GetValue().lower()
        

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
        label1a = wx.StaticText(self, -1, "max Download speed (kb/s):")
        label1a.SetToolTipString('Restricts the client to not download more kilobytes per second then set here')
        limiterItems.Add(label1a, 1, wx.EXPAND)
        
        self.spin1 = wx.SpinCtrl(self, -1, size=wx.Size(80,-1))
        self.spin1.SetRange(1, 1048576)
        self.spin1.SetValue(self.config.getInt('network','downSpeedLimit')/1024)
        self.spin1.SetToolTipString('Restricts the client to not download more kilobytes per second then set here')
        limiterItems.Add(self.spin1, 1)

        #up speed        
        label2a = wx.StaticText(self, -1, "max Upload speed (kb/s):")
        label2a.SetToolTipString('Restricts the client to not upload more kilobytes per second then set here')
        limiterItems.Add(label2a, 1, wx.EXPAND)
        
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
        samOptionBoxItems.Add(label1a, 1, wx.EXPAND)
        
        self.ipField1 = IpAddrCtrl(self, -1)
        self.ipField1.SetValue(self.config.get('i2p','samIp'))
        self.ipField1.SetToolTipString('Enter the IP address of the Sam bridge here')
        samOptionBoxItems.Add(self.ipField1, 1)
        
        
        #port of sam bridge
        label2a = wx.StaticText(self, -1, "Sam port:")
        label2a.SetToolTipString('Enter the port of the Sam bridge here')
        samOptionBoxItems.Add(label2a, 1, wx.EXPAND)
        
        self.spin1 = wx.SpinCtrl(self, -1, size=wx.Size(115,-1))
        self.spin1.SetRange(1, 65535)
        self.spin1.SetValue(self.config.getInt('i2p','samPort'))
        self.spin1.SetToolTipString('Enter the port of the Sam bridge here')
        samOptionBoxItems.Add(self.spin1, 1)
        
        
        #sam display name
        label3a = wx.StaticText(self, -1, "Display name:")
        label3a.SetToolTipString('This name will appear in the destinations overview of the i2p router webinterface.')
        samOptionBoxItems.Add(label3a, 1, wx.EXPAND)
        
        self.edit1 = wx.TextCtrl(self, -1, "", size=wx.Size(115,-1))
        self.edit1.SetValue(self.config.get('i2p','samDisplayName'))        
        self.edit1.SetToolTipString('This name will appear in the destinations overview of the i2p router webinterface.')
        samOptionBoxItems.Add(self.edit1, 1)
        
        
        #sam session name
        label4a = wx.StaticText(self, -1, "Session name:")
        label4a.SetToolTipString('This name will be used by the sam bridge to determine which i2p destination should be used for this client, changing it will also change the used destination.')
        samOptionBoxItems.Add(label4a, 1, wx.EXPAND)
        
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
        tunnelOptionBoxItems.Add(label6a, 1, wx.EXPAND)
        
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
        tunnelOptionBoxItems.Add(label7a, 1, wx.EXPAND)
        
        self.spin2In = wx.SpinCtrl(self, -1, size=wx.Size(80,-1))
        self.spin2In.SetRange(1, 3)
        self.spin2In.SetValue(self.config.getInt('i2p','samNumOfTunnelsIn'))
        self.spin2In.SetToolTipString('Number of inbound tunnels')
        tunnelOptionBoxItems.Add(self.spin2In, 1)
        
        self.spin2Out = wx.SpinCtrl(self, -1, size=wx.Size(80,-1))
        self.spin2Out.SetRange(1, 3)
        self.spin2Out.SetValue(self.config.getInt('i2p','samNumOfTunnelsOut'))
        self.spin2Out.SetToolTipString('Number of outbound tunnels')
        tunnelOptionBoxItems.Add(self.spin2Out, 1)
        
        
        #backup tunnel quantity
        label8a = wx.StaticText(self, -1, "Number of backup tunnels:")
        label8a.SetToolTipString('Number of backup tunnels')
        tunnelOptionBoxItems.Add(label8a, 1, wx.EXPAND)
        
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
        tunnelOptionBoxItems.Add(label9a, 1, wx.EXPAND)
        
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
        tunnelOptionBoxItems.Add(label10a, 1, wx.EXPAND)
        
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
                                               'Both the display and session name must be unique for the used i2p router. If "TRANSIENT" (without the quotes) is used as a session name, the client will get a different i2p destination after each reconnect to the i2p router.')
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
        optionDict[('i2p', 'samDisplayName')] = self.edit1.GetValue().replace(' ', '')
        optionDict[('i2p', 'samSessionName')] = self.edit2.GetValue().replace(' ', '')
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
        pathsRealItems.Add(label2, 1)

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
        pathsRealItems.Add(label3, 1)
        
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
        
        


class ConfigDialog(wx.Frame):
    def __init__(self, config, parent, **kwargs):
        wx.Frame.__init__(self, parent, -1, 'Preferences', size=wx.Size(550, 475),\
                          style = wx.DEFAULT_FRAME_STYLE | wx.STAY_ON_TOP, **kwargs)
        self.CentreOnScreen()
        self.config = config

        self.hBox = wx.BoxSizer(wx.HORIZONTAL)
        self.vBox = wx.BoxSizer(wx.VERTICAL)
        #tree
        self.tree = wx.TreeCtrl(parent=self, id=100, size=wx.Size(150,-1),\
                                style=wx.TR_DEFAULT_STYLE | wx.TR_HIDE_ROOT | wx.TR_HAS_BUTTONS | wx.TR_SINGLE )
        root = self.tree.AddRoot('root')
        n10 = self.tree.AppendItem(root, "Logging")
        n20 = self.tree.AppendItem(root, "Network")
        n21 = self.tree.AppendItem(n20,  "I2P")
        n30 = self.tree.AppendItem(root, "Paths")
        
        self.tree.Expand(n10)
        self.tree.Expand(n20)
        self.tree.Expand(n21)
        self.tree.Expand(n30)
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
        self.configPanels = {'Logging':Logging_ConfigPanel(self.config, self),\
                             'Network':Network_ConfigPanel(self.config, self),\
                             'I2P':I2P_ConfigPanel(self.config, self),\
                             'Paths':Paths_ConfigPanel(self.config, self)}
        self.activePanel = 'Logging'
        
        for panelName in self.configPanels.keys():
            if not panelName==self.activePanel:
                self.configPanels[panelName].Hide()
            self.hBox.Add(self.configPanels[panelName], 1, wx.EXPAND)

        #Line everything up
        self.SetSizer(self.hBox)
        self.Layout()
        
        #events
        self.Bind(wx.EVT_TREE_SEL_CHANGED, self.OnTreeSelectChange, id=100)
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
        self.config.setMany(optionDict, True)
        self.Destroy()
        

    def OnClose(self, event):
        self.Destroy()
        

if __name__ == "__main__":
    from Config import Config
    
    #gui config options
    configDefaults = {'logging':{'consoleLoglevel':('critical', 'str'),
                                 'fileLoglevel':('info', 'str')},
                      'paths':{'torrentFolder':('/tmp', 'str'),
                               'downloadFolder':('/tmp', 'str')}}
                    
    #bt config options
    btConfigDefaults = {'network':{'downSpeedLimit':(102400, 'int'),
                                   'upSpeedLimit':(10240, 'int')},
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
                               'samTunnelLengthVarianceOut':(1, 'int')}}
                                    
    #create config, add bt defaults
    config = Config('config.conf', configDefaults=configDefaults)
    config.addDefaults(btConfigDefaults)
    
    #create GUI
    app = wx.App()
    merk = ConfigDialog(config,None)
    app.MainLoop()
