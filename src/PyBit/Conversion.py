"""
Copyright 2009  Blub

Conversion.py, a collection of functions for converting certain data types into string and the other way around.
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

from time import localtime, mktime, strptime

##string - specific convert funcs

def stringToDataAmount(string):
    t = {'B ':1,'Kb':1024,'Mb':1048576,'Gb':1073741824}
    if not string[-2:] in t:
        amount = 0
    else:
        try:
            amount = t[string[-2:]] * float(string[:-2])
        except ValueError:
            amount = 0
    return int(dataAmount)


def stringToTimeInterval(string):
    t = {'s':1,'m':60,'h':3600,'d':86400}
    timeInt = 0
    strList = timeString.split(' ')
    for timeStr in strList:
        if timeStr[-1] in t:
            try:
                timeInt += t[timeStr[-1]] * int(timeStr[:-1])
            except ValueError:
                pass
    return timeInt


def stringToPeerStats(string):
    data = []
    for num in string[:-1].split(' ('):
        data.append(int(num))
    return data


def stringToPercent(perc):
    return float(perc[:-1])


def stringToBool(string):
    if string=='*':
        return True
    else:
        return False
    

def stringToTransferSpeed(string):
    return stringToDataAmount(string[:-2])


def stringToDate(string):
    timeTuple = strptime(string,'%d.%m.%Y')
    value = mktime(timeTuple)
    return value


def stringToFullTime(string):
    timeTuple = strptime(string,'%H:%M:%S, %d.%m.%Y')
    value = mktime(timeTuple)
    return value


##string - dict

stringToDataFuncs = {'float':float,\
                     'int':int,\
                     'str':str,\
                     'native':lambda x: x,\
                     'date':stringToDate,\
                     'fullTime':stringToFullTime,\
                     'timeInterval':stringToTimeInterval,\
                     'peerStats':stringToPeerStats,\
                     'percent':stringToPercent,\
                     'dataAmount':stringToDataAmount,\
                     'transferSpeed':stringToTransferSpeed,\
                     'bool':stringToBool}


##string - general convert func

def stringToData(dataType, string):
    return stringToDataFuncs[dataType](string)


##data - specific convert funcs


def dataAmountToString(dataAmount, roundToDigits=2):
    t = [['Kb', 1024.0], ['Mb', 1024.0], ['Gb', 1024.0]]
    end = 'B '
    while dataAmount/t[0][1] > 1:
        dataAmount = dataAmount / t[0][1]
        end = t[0][0]
        del t[0]
        if len(t) == 0:
            break
    value = str(round(dataAmount, roundToDigits)) + end
    return value


def timeIntervalToString(timeLeft, max=365):
    t = [['m', 60.0], ['h', 60.0], ['d', 24.0]]
    end = 's'
    while timeLeft / t[0][1] > 1:
        left = timeLeft % t[0][1]
        timeLeft = (timeLeft - left) / t[0][1]
        end = ''.join((t[0][0], ' ', str(int(left)), end))
        del t[0]
        if len(t)==0:
            break
        
    if timeLeft > max:
        timeLeft = max
    return str(int(round(timeLeft,0))) + end


def peerStatsToString(statTup):
    return ''.join((str(statTup[0]), ' (', str(statTup[1]), ')'))


def percentToString(zahl, roundToDigits=2):
    return str(round(zahl,roundToDigits)) + '%'


def transferSpeedToString(zahl):
    return dataAmountToString(zahl) + '/s'


def boolToString(wert):
    if wert:
        return '*'
    else:
        return ' '


def dateToString(timestamp):
    timeTuple = localtime(timestamp)
    value = '.'.join((str(timeTuple[2]), str(timeTuple[1]), str(timeTuple[0])))
    return value


def fullTimeToString(timestamp):
    timeTuple = localtime(timestamp)
    timeList = []
    for i in xrange(0, len(timeTuple)):
        timeStr = str(timeTuple[i])
        if len(timeStr) == 1:
            timeList.append('0' + timeStr)
        else:
            timeList.append(timeStr)
    value = ''.join((timeList[3], ':', timeList[4], ':', timeList[5], ', ', timeList[2], '.', timeList[1], '.', timeList[0]))
    return value


##data - dict

dataToStringFuncs  = {'float':str,\
                      'int':str,\
                      'str':str,\
                      'native':lambda x: x,\
                      'date':dateToString,\
                      'fullTime':fullTimeToString,\
                      'timeInterval':timeIntervalToString,\
                      'peerStats':peerStatsToString,\
                      'percent':percentToString,\
                      'dataAmount':dataAmountToString,\
                      'transferSpeed':transferSpeedToString,\
                      'bool':boolToString}    

##string - general convert func

def dataToString(dataType, value):
    return dataToStringFuncs[dataType](value)