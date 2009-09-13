"""
Copyright 2009  Blub

SortableList, a general class which creates a dialog which represents a table with
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
import threading
import wx

import Conversion

    
class SortableList(wx.ListView):
    def __init__(self, cols, updateFunc, parent, customDataToStringFuncs=[], customStringToDataFuncs=[],\
                 changeableCols=True, sortable=True, id=-1, pos=wx.DefaultPosition, size=wx.DefaultSize, style=wx.LC_REPORT | wx.LC_VRULES, **kwargs):
        wx.ListView.__init__(self, parent, id, pos, size, style, **kwargs)
        
        #get a copy of the converter dicts
        self.dataToStringFuncs = copy(Conversion.dataToStringFuncs)
        self.stringToDataFuncs = copy(Conversion.stringToDataFuncs)

        #add custom funcs
        for funcTup in customDataToStringFuncs:
            if not funcTup[0] in self.dataToStringFuncs:
                self.dataToStringFuncs[funcTup[0]]=funcTup[1]
        
        for funcTup in customStringToDataFuncs:
            if not funcTup[0] in self.stringToDataFuncs:
                self.stringToDataFuncs[funcTup[0]]=funcTup[2]
            
        self.colData = {} #static info stuff
        self.colMapper = [] #maps a column name to a position
        self.watchedCols = [] #keeps track of columns which should be 'watched'
        self.watchedColsData = {} #contains the real data of the 'watched' cols

        #add columns, build up mapper and data dict
        place = 0
        while place < len(cols):
            if cols[place][3]==True:
                self.watchedCols.append(cols[place][0])
                self.watchedColsData[cols[place][0]]=[]
            self.colData[cols[place][0]] = {'statName':cols[place][1],\
                                            'statType':cols[place][2]}
            self.colMapper.append(cols[place][0])
            self.InsertColumn(place, cols[place][0])
            if cols[place][4] is not None:
                self.SetColumnWidth(place, cols[place][4])
            place += 1

        self.colNum = len(cols) #number of columns

        #sorting vars
        self.sortColumn = 0
        self.sortDirection = 'ASC'

        self.updateFunc = updateFunc #function to get data from

        self.lock = threading.RLock() #guess... (recursive lock)

        if sortable:
            self.Bind(wx.EVT_LIST_COL_CLICK, self.OnColClick) #sort on col click
            
        if changeableCols:
            self.Bind(wx.EVT_LIST_COL_RIGHT_CLICK, self.OnColRightClick) #display options on right click on col
    
    
    ##internal functions - other

    def _getData(self, colName, index):
        return self.watchedColsData[colName][index]
    

    def _getColumnFromPosition(self, x):
        clickPos = self.GetScrollPos(wx.HORIZONTAL) + x
        clickedCol = -1
        pos = 0
        while pos <= clickPos:
            clickedCol += 1
            if clickedCol<self.colNum:
                pos += self.GetColumn(clickedCol).GetWidth()
            else:
                clickedCol = None
                break
        return clickedCol
    

    def _insertColumn(self, place, name):
        listItm = wx.ListItem
        self.InsertColumnItem(place, listItm)
        

    def _getStatData(self, statData, colName):
        statName = self.colData[colName]['statName']
        if type(statName)==str:
            data = statData[statName]
        else:
            data = []
            for name in statName:
                data.append(statData[name])
        return data
    
    
    ##internal functions - rows
        
    def _addRow(self, data):
        dataSet = []
        for colNum in xrange(0, self.colNum):
            colName = self.colMapper[colNum]
            #get data
            statData = self._getStatData(data, colName)                          
            #convert data
            statData = self.dataToStringFuncs[self.colData[colName]['statType']](statData)
            #add data to plain list
            dataSet.append(statData)
        #add complete list as a row to the gui list
        self.Append(dataSet)
        self.Update()
        
        
    def _updateRow(self, rowInd, data):  
        anythingChanged = False
        for colNum in xrange(0, self.colNum):
            colName = self.colMapper[colNum]            
            #get data
            statData = self._getStatData(data, colName)              
            #convert data
            statData = self.dataToStringFuncs[self.colData[colName]['statType']](statData)            
            #update list item
            listItm = self.GetItem(rowInd, col=colNum)
            if not listItm.GetText() == statData:
                listItm.SetText(statData)
                anythingChanged = True
            self.SetItem(listItm)
            #self.SetStringItem(rowInd, colNum, stat) #update list
        if anythingChanged==True:
            self.Update()
            
    
    ##event functions - columns

    def OnColClick(self, event):
        self.lock.acquire()
        clickedCol = event.GetColumn()
        if not clickedCol == self.sortColumn:
            self.sortColumn = clickedCol
            self.sortDirection = 'ASC'
        else:
            if self.sortDirection == 'ASC':
                self.sortDirection = 'DESC'
            else:
                self.sortDirection = 'ASC'
        self.dataUpdate()
        #event.Skip()
        self.lock.release()
        
        
    def OnColRightClick(self, event):
        self.lock.acquire()
        cols = []
        for colName in self.colData.keys():
            active = (colName in self.colMapper)
            cols.append((colName, active))
        cols.sort()
        clickedCol = self._getColumnFromPosition(event.GetPosition().Get()[0])
        if clickedCol == None:
            merk = ColumnSelection(cols, self.enableCol, self.disableCol, None, self.moveCol)
        else:
            merk = ColumnSelection(cols, self.enableCol, self.disableCol, self.colMapper[clickedCol], self.moveCol)
        self.PopupMenu(merk)
        #event.Skip()
        self.lock.release()
    
    
    ##external functions - columns

    def disableCol(self, colName):
        self.lock.acquire()
        if self.colNum>1:
            #ok to disable column, its not the last one
            colPos = self.colMapper.index(colName)
            del self.colMapper[colPos]
            self.colNum -= 1
            self.DeleteColumn(colPos)

            #clean the whole sorting stuff up
            if self.sortColumn==colPos:
                #we delete the row which is responsible for sorting the whole stuff, default back to the first col
                self.sortColumn = 0
                self.sortDirection = 'ASC'
            elif self.sortColumn>colPos:
                #we sort depending on a column which is after the deleted column
                self.sortColumn -= 1
        self.lock.release()
        

    def enableCol(self, colName):
        self.lock.acquire()
        self.InsertColumn(self.colNum, colName)        
        self.colMapper.insert(self.colNum, colName)
        self.colNum += 1
        
        self.lock.release()
        self.dataUpdate()
        

    def moveCol(self, colName, direction):
        self.lock.acquire()
        colPos = self.colMapper.index(colName)
        if (colPos + direction)>=0 and (colPos + direction)<self.colNum:
            self.DeleteColumn(colPos)
            self.InsertColumn(colPos + direction, colName)
            del self.colMapper[colPos]
            self.colMapper.insert(colPos + direction, colName)

            #clean the whole sorting stuff up
            if direction <= 0 and self.sortColumn < colPos and self.sortColumn >= colPos+direction:                
                self.sortColumn += (direction * -1)
            elif direction > 0 and self.sortColumn > colPos and self.sortColumn <= colPos+direction:
                self.sortColumn += direction
            elif self.sortColumn == colPos:
                self.sortColumn += direction
        self.lock.release()
        self.dataUpdate()
        
        
    ##update

    def dataUpdate(self):
        self.lock.acquire()
        stats = self.updateFunc()        
        rowNumber = self.GetItemCount()

        #empty watchlist
        for colName in self.watchedCols:
            self.watchedColsData[colName]=[] 
        
        #delete rows if there are too many
        while rowNumber > len(stats):
            self.DeleteItem(0)
            rowNumber -= 1
            self.Update()
        
        #create SortList
        sortList = []
        colName = self.colMapper[self.sortColumn] #Name of Column which is used for sorting
        place = 0
        while place < len(stats):
            sortList.append((self._getStatData(stats[place],colName), place))
            place += 1
        sortList.sort()
        if self.sortDirection == 'DESC':
            sortList.reverse()

        #overwrite existing rows
        row = 0
        while row<rowNumber:
            rawStatData = stats[sortList[0][1]]
            #add to watchlists
            for colName in self.watchedCols:
                statData = self._getStatData(rawStatData, colName)
                self.watchedColsData[colName].append(statData)
            #update
            self._updateRow(row, rawStatData)
            del sortList[0]
            row += 1

        #create new rows if necessary
        while len(sortList)>0:
            rawStatData = stats[sortList[0][1]]
            #add to watchlists
            for colName in self.watchedCols:
                statData = self._getStatData(rawStatData, colName)
                self.watchedColsData[colName].append(statData)
            #update
            self._addRow(rawStatData)
            del sortList[0]
            
        self.lock.release()


class ColumnSelection(wx.Menu):
    def __init__(self, cols, enableFunc, disableFunc, clickedCol, moveFunc, *args, **kwargs):
        wx.Menu.__init__(self, *args, **kwargs)
        #static
        self.enableCol = enableFunc
        self.disableCol = disableFunc
        self.clickedCol = clickedCol
        self.moveCol = moveFunc

        if not clickedCol==None:
            #left/right
            m = wx.MenuItem(parentMenu=self,text='Move to Left')
            self.AppendItem(m)
            self.Bind(wx.EVT_MENU, self.OnMoveToLeft, m)
            
            m = wx.MenuItem(parentMenu=self,text='Move to Right')
            self.AppendItem(m)
            self.Bind(wx.EVT_MENU, self.OnMoveToRight, m)

            self.AppendSeparator()
        
        #enable/disable columns
        self.idMapper = {}
        for tup in cols:
            m = wx.MenuItem(parentMenu=self,text=tup[0])
            m.SetCheckable(True)
            self.AppendItem(m)
            if tup[1]==True:
                m.Toggle()
            self.idMapper[m.GetId()]=tup[0]
            
            #event
            self.Bind(wx.EVT_MENU, self.OnClick, m)
            
        

    def OnClick(self, event):
        colName = self.idMapper[event.GetId()]
        if event.IsChecked()==True:
            self.enableCol(colName)
        else:
            self.disableCol(colName)
        #event.Skip(False)
        

    def OnMoveToLeft(self, event):
        self.moveCol(self.clickedCol, -1)
        

    def OnMoveToRight(self, event):
        self.moveCol(self.clickedCol, 1)
            
