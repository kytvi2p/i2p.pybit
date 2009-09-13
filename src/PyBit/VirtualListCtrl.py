"""
Copyright 2009  Blub

VirtualListCtrl, a general class which creates a dialog which represents a table with
(user selectable) columns and rows, sortable by column.
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

from copy import copy
import sys
import threading
import wx

import Conversion


class VirtualListCtrl(wx.ListCtrl):
    def __init__(self, cols, updateFunc, parent, customDataToStringFuncs=[], id=-1,
                 pos=wx.DefaultPosition, size=wx.DefaultSize, style=wx.LC_REPORT | wx.LC_VIRTUAL | wx.LC_VRULES, **kwargs):
        wx.ListCtrl.__init__(self, parent, id, pos, size, style, **kwargs)
        """
        cols:
            [(*columnName*, *dataKeyword*, *dataType*, *columnWidth*), ...]
        """
        self.updateFunc = updateFunc
        
        #get a copy of the converter dicts
        self.dataToStringFuncs = copy(Conversion.dataToStringFuncs)
        
        #add custom funcs
        for funcTup in customDataToStringFuncs:
            if not funcTup[0] in self.dataToStringFuncs:
                self.dataToStringFuncs[funcTup[0]]=funcTup[1]
                
        #columns
        self.colData = {}
        self.colInfo = {} #static info stuff
        self.colMapper = [] #maps a column name to a position
        
        #add columns, build up mapper and data dict
        place = 0
        while place < len(cols):
            colSet = cols[place]
            self.colData[colSet[0]] = []
            self.colInfo[colSet[0]] = {'colPos':place,\
                                       'dataKeyword':colSet[1],\
                                       'dataType':colSet[2]}
            self.colMapper.append(colSet[0])
            self.InsertColumn(place, colSet[0])
            if colSet[3] is not None:
                self.SetColumnWidth(place, colSet[3])
            place += 1

        self.colNum = place #number of columns
        
        #sorting vars
        self.sortColumn = 0
        self.sortDirection = 'ASC'
        
        #lock
        self.lock = threading.RLock() #guess...
        
        #events
        self.Bind(wx.EVT_LIST_COL_CLICK, self.OnColClick) #sort on col click
        self.Bind(wx.EVT_LIST_COL_RIGHT_CLICK, self.OnColRightClick) #display options on right click on col
        
        #tell ListCtrl how many items we currently have
        self.SetItemCount(0)
        
        
    ##internal functions
    
    def _getRawData(self, colName, rowIndex):
        return self.colData[colName][rowIndex]
        
        
    def _dataUpdate(self, data):
        oldDataAmount = len(self.colData[self.colMapper[0]])
        
        #create sort list
        colName = self.colMapper[self.sortColumn]
        dataKeyword = self.colInfo[colName]['dataKeyword']
        if type(dataKeyword)==str:
            #single item
            sortList = [row[dataKeyword] for row in data]
        else:
            #multiple items
            sortList = []
            for row in data:
                sortList.append(tuple([row[singleDataKeyword] for singleDataKeyword in dataKeyword]))
        
        #add row index
        sortList = map(lambda tup: (tup[1], tup[0]), enumerate(sortList))
        
        #sort the list
        sortList.sort()
        if self.sortDirection == 'DESC':
            sortList.reverse()
            
        #create new data list
        for colName in self.colData.keys():
            #fill one column
            colDataKeyword = self.colInfo[colName]['dataKeyword']
            if type(colDataKeyword)==str:
                #only a single data item
                self.colData[colName] = list([data[rowNum][colDataKeyword] for rowData, rowNum in sortList])
                
            else:
                #multiple data items
                colData = []
                for rowData, rowNum in sortList:
                    colData.append(list([data[rowNum][singleDataKeyword] for singleDataKeyword in colDataKeyword]))
                self.colData[colName] = colData
                
        #set new item length if rows got added or removed
        newDataAmount = len(sortList)
        if newDataAmount != oldDataAmount:
            self.SetItemCount(newDataAmount)
                
        #refresh currently displayed items
        firstDisplayedRow = self.GetTopItem()
        lastDisplayedRow = min(firstDisplayedRow + self.GetCountPerPage(), newDataAmount)
        self.RefreshItems(firstDisplayedRow, lastDisplayedRow)
        
        #windows is a bit strange and requires this call - welcome flickering, here you go ...
        if sys.platform == 'win32':
            self.Refresh()
            
    
    ##event functions

    def OnColClick(self, event):
        self.lock.acquire()
        clickedCol = event.GetColumn()
        if not clickedCol == self.sortColumn:
            #use another column for sorting stuff
            self.sortColumn = clickedCol
            self.sortDirection = 'ASC'
        else:
            #just reverse sorting order
            if self.sortDirection == 'ASC':
                self.sortDirection = 'DESC'
            else:
                self.sortDirection = 'ASC'
        
        self.dataUpdate()
        self.lock.release()
        
        
    def OnColRightClick(self, event):
        self.lock.acquire()
        cols = []
        for colName in self.colData.iterkeys():
            active = (colName in self.colMapper)
            cols.append((colName, active))
        cols.sort()
        
        clickedCol = event.GetColumn()
        if clickedCol == -1:
            merk = ColumnSelectionPopup(cols, self.enableCol, self.disableCol, None, self.moveCol)
        else:
            merk = ColumnSelectionPopup(cols, self.enableCol, self.disableCol, self.colMapper[clickedCol], self.moveCol)
        self.PopupMenu(merk)
        self.lock.release()
        
        
    def OnGetItemText(self, rowIndex, columnIndex):
        self.lock.acquire()
        colName = self.colMapper[columnIndex]
        data = self.colData[colName][rowIndex]
        data = self.dataToStringFuncs[self.colInfo[colName]['dataType']](data)
        self.lock.release()
        return data
    
    
    ##external functions - columns

    def disableCol(self, colName):
        self.lock.acquire()
        if self.colNum > 1:
            #ok to disable column, its not the last one
            colPos = self.colMapper.index(colName)
            del self.colMapper[colPos]
            self.colNum -= 1
            self.DeleteColumn(colPos)

            #clean the whole sorting stuff up
            if self.sortColumn == colPos:
                #we deleted the row which is used for sorting, default back to the first col
                self.sortColumn = 0
                self.sortDirection = 'ASC'
                
            elif self.sortColumn>colPos:
                #we sort depending on a column which is after the deleted column
                self.sortColumn -= 1
                
        self.lock.release()
        

    def enableCol(self, colName):
        self.lock.acquire()
        self.InsertColumn(self.colNum, colName)        
        self.colMapper.append(colName)
        self.colNum += 1
        self.dataUpdate()
        self.lock.release()
        

    def moveCol(self, colName, direction):
        self.lock.acquire()
        colPos = self.colMapper.index(colName)
        if (colPos + direction) >= 0 and (colPos + direction) < self.colNum:
            self.DeleteColumn(colPos)
            self.InsertColumn(colPos + direction, colName)
            del self.colMapper[colPos]
            self.colMapper.insert(colPos + direction, colName)

            #clean the whole sorting stuff up
            if direction < 0 and self.sortColumn < colPos and self.sortColumn >= colPos+direction:                
                self.sortColumn += 1
                
            elif direction > 0 and self.sortColumn > colPos and self.sortColumn <= colPos+direction:
                self.sortColumn -= 1
                
            elif self.sortColumn == colPos:
                self.sortColumn += direction
                
        self.dataUpdate()
        self.lock.release()
        
        
    ##external functions - data
    
    def clear(self):
        self.lock.acquire()
        self._dataUpdate([])
        self.lock.release()
        
        
    def changeUpdateFunc(self, updateFunc):
        self.lock.acquire()
        self.updateFunc = updateFunc
        self.lock.release()
        
    
    def dataUpdate(self):
        self.lock.acquire()
        data = self.updateFunc()
        self._dataUpdate(data)
        self.lock.release()




class ColumnSelectionPopup(wx.Menu):
    def __init__(self, cols, enableFunc, disableFunc, clickedCol, moveFunc, *args, **kwargs):
        wx.Menu.__init__(self, *args, **kwargs)
        #static
        self.enableCol = enableFunc
        self.disableCol = disableFunc
        self.clickedCol = clickedCol
        self.moveCol = moveFunc

        if clickedCol is not None:
            #left/right
            id = wx.NewId()
            self.Append(id, 'Move to left', 'Moves column one step to the left')
            self.Bind(wx.EVT_MENU, self.OnMoveToLeft, id=id)
            
            id = wx.NewId()
            self.Append(id, 'Move to right', 'Moves column one step to the right')
            self.Bind(wx.EVT_MENU, self.OnMoveToRight, id=id)

            self.AppendSeparator()
        
        #enable/disable columns
        self.idMapper = {}
        for tup in cols:
            id = wx.NewId()
            m = self.AppendCheckItem(id, tup[0], 'Activates or deactivates this column')
            #m.SetCheckable(True)
            if tup[1]==True:
                m.Toggle()
            self.idMapper[id]=tup[0]
            
            #event
            self.Bind(wx.EVT_MENU, self.OnClick, id=id)
            
        

    def OnClick(self, event):
        colName = self.idMapper[event.GetId()]
        if event.IsChecked() == True:
            self.enableCol(colName)
        else:
            self.disableCol(colName)
        #event.Skip(False)
        

    def OnMoveToLeft(self, event):
        self.moveCol(self.clickedCol, -1)
        

    def OnMoveToRight(self, event):
        self.moveCol(self.clickedCol, 1)
            
        
        
if __name__ == "__main__":
    app = wx.App()
    merk = Testframe()
    app.MainLoop()