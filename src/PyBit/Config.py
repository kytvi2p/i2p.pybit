"""
Copyright 2009  Blub

Config, a class which handles the storing and retrieving of options from the config file.
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

from __future__ import with_statement
from collections import defaultdict
from ConfigParser import SafeConfigParser
import logging
import os
import re
import threading




class ConfigException(Exception):
    pass




class Config:
    def __init__(self, configFile='config.conf', configDefaults={}):
        self.configFile = configFile
        
        #permanent structures
        self.log = logging.getLogger('Config')
        self.ipCheck = re.compile('^((25[0-5])|(2[0-4][0-9])|([1]??[1-9]??[0-9]))(.((25[0-5])|(2[0-4][0-9])|([1]??[1-9]??[0-9]))){3,3}$')
        self.config = SafeConfigParser()
        self.callbackManager = ConfigCallbackManager(self.get)
        self.configDefaults = defaultdict(dict)
        
        #load config file
        self._readConfig()
        
        #set internal structures
        self._addDefaults(configDefaults)
        self._setDefaults(self.configDefaults)
        
        #write config
        self._writeConfig()
        
        #main lock
        self.lock = threading.RLock()
        
        
    ##internal functions - config file
    
    def _readConfig(self):
        #create config file if it doesn't exist
        if os.path.isfile(self.configFile)==False:
            self.log.warn("Didn't find a config file, creating one.")
            try:
                fl = open(self.configFile, 'wb')
                fl.close()
            except:
                self.log.warn("Failed to create config file!")
            
        #read config file
        readFiles = self.config.read(self.configFile)
        if len(readFiles)==0:
            self.log.warn("Failed to read config file!")
        
    
    def _writeConfig(self):
        #write config
        self.log.debug("Trying to write options back to config file")
        try:
            fl = open(self.configFile, 'wb')
            with fl:
                self.config.write(fl)
                fl.close()
        except:
            self.log.warn("Failed to write to config file!")
            
            
    ##internal functions - option types
    
    def _getOptionType(self, section, option):
        return self.configDefaults[section][option][1]
    
        
    def _checkOptionType(self, section, option, optionData, optionType):
        ok = False
        if optionType=='str':
            ok = True
            
        elif optionType=='int':
            try:
                int(optionData)
                ok = True
            except:
                pass
            
        elif optionType=='long':
            try:
                long(optionData)
                ok = True
            except:
                pass
            
        elif optionType=='float':
            try:
                float(optionData)
                ok = True
            except:
                pass
                
        elif optionType=='bool':
            if str(optionData).lower() in ('true', 'false'):
                ok = True
            
        elif optionType=='ip':
            if self.ipCheck.match(optionData) is not None:
                ok = True
                
        elif optionType=='port':
            try:
                port = int(optionData)
                if port > 0 and port < 65536:
                    ok = True
            except:
                pass
        
        return ok
    
    
    def _applyOptionType(self, section, option, optionDataAsString, optionType):
        data = optionDataAsString
        
        if optionType=='int':
            data = int(optionDataAsString)
            
        elif optionType=='long':
            data = long(optionDataAsString)
            
        elif optionType=='float':
            data = float(optionDataAsString)
                
        elif optionType=='bool':
            data = optionDataAsString.lower() == 'true'
                
        elif optionType=='port':
            data = int(optionDataAsString)
            
        return data
        
        
    ##internal functions - defaults
    
    def _addDefaults(self, configDefaults):
        for section in configDefaults.iterkeys():
            for name, value in configDefaults[section].iteritems():
                self.configDefaults[section][name] = value
                
    
    def _setDefaults(self, configDefaults):
        #set default options if not already set
        for section in configDefaults.iterkeys():
            if not self.config.has_section(section):
                #section doesn't exist, create it
                self.config.add_section(section)
                
            for name in configDefaults[section].iterkeys():
                if not self.config.has_option(section, name):
                    #option isn't known, add it
                    self.log.warn('The option in section "%s" with name "%s" does not exist, setting it to the default value "%s"!',
                                  section, name, str(configDefaults[section][name][0]))
                    self.config.set(section, name, str(configDefaults[section][name][0]))
                elif not self._checkOptionType(section, name, self.config.get(section, name), configDefaults[section][name][1]):
                    #options exists but has the wrong type, replace it
                    self.log.warn('The option in section "%s" with name "%s" and value "%s" has the wrong type, setting it to the default value "%s"!',
                                  section, name, self.config.get(section, name), str(configDefaults[section][name][0]))
                    self.config.set(section, name, str(configDefaults[section][name][0]))
    
    
    ##external functions - defaults
    
    def addDefaults(self, configDefaults):
        self.lock.acquire()
        self._addDefaults(configDefaults)
        self._setDefaults(configDefaults)
        self.lock.release()
        
        
    ##external functions - callbacks
    
    def addCallback(self, options, func, funcArgs=[], funcKw={}, valueArgPlace=0, callType='value-funcArgSingle', optionTranslationTable={}, callWithAllOptions=False):
        self.lock.acquire()
        callbackId = self.callbackManager.addCallback(options, func, funcArgs, funcKw, valueArgPlace, callType, optionTranslationTable, callWithAllOptions)
        self.lock.release()
        return callbackId
    
    
    def removeCallback(self, callbackId):
        self.lock.acquire()
        self.callbackManager.removeCallback(callbackId)
        self.lock.release()
        
        
    ##external functions - checks
        
    def hasSection(self, section):
        self.lock.acquire()
        result = self.config.has_section(section)
        self.lock.release()
        return result
    
    
    def hasOption(self, section, option):
        self.lock.acquire()
        result = self.config.has_option(section, option)
        self.lock.release()
        return result
    
        
    ##external functions - getter and setter
    
    
    def get(self, section, name):
        with self.lock:
            result = self.config.get(section, name)
            result = self._applyOptionType(section, name, result, self._getOptionType(section, name))
        return result
    
    def getStr(self, section, name):
        with self.lock:
            result = self.config.get(section, name)
        return result
    

    def getInt(self, section, name):
        with self.lock:
            result = int(self.config.get(section, name))
        return result
    

    def getBool(self, section, name):
        with self.lock:
            result = self.config.get(section, name)
            result = result.lower() == 'true'
        return result
    

    def getFloat(self, section, name):
        with self.lock:
            result = float(self.config.get(section, name))
        return result
    

    def set(self, section, name, value, quiet=False):
        #set value
        with self.lock:
            if not self._checkOptionType(section, name, value, self._getOptionType(section, name)):
                if not quiet:
                    raise ConfigException('Invalid type: section "%s", name "%s": expected "%s", got "%s" (value: "%s")' % (section, name, self._getOptionType(section, name), str(type(value)), str(value)))
            else:
                if str(value) != self.config.get(section, name):
                    #value changed
                    self.config.set(section, name, str(value))
                    self.callbackManager.execCallbacks({(section, name):value})
                    self._writeConfig()
        
        
    def setMany(self, options, quiet=False):
        with self.lock:
            changedOptions = {}
            #check which options changed (and if they have the right type)
            for option, value in options.iteritems():
                if not self._checkOptionType(option[0], option[1], value, self._getOptionType(option[0], option[1])):
                    #wrong type
                    if not quiet:
                        raise ConfigException('Invalid type: section "%s", option "%s": expected "%s", got "%s" (value: "%s")' % (option[0], option[1], self._getOptionType(option[0], option[1]), str(type(value)), str(value)))
                else:
                    #right type
                    if str(value) != self.config.get(option[0], option[1]):
                        #value changed
                        self.log.debug('Option in section "%s" with name "%s" changed, new value "%s"', option[0], option[1], str(value))
                        changedOptions[option] = value
                    else:
                        self.log.debug('Option in section "%s" with name "%s" did not change', option[0], option[1])
            
            #set options
            for option, value in changedOptions.iteritems():
                self.config.set(option[0], option[1], str(value))
            
            #write to config file and call callbacks if necessary
            if len(changedOptions) > 0:
                #some options were really changed
                self.callbackManager.execCallbacks(changedOptions)
                self._writeConfig()
        
        
        
        
class ConfigCallbackManager:
    def __init__(self, valueGetFunc):
        self.valueGetFunc = valueGetFunc
        self.nextCallbackId = 0
        self.callbackObjs = {}
        self.optionsToCallbackId = defaultdict(lambda: defaultdict(set))
        self.log = logging.getLogger('ConfigCallbackManager')
        
        
    def _fillOptionDict(self, neededOptions, callOptions):
        for option in neededOptions:
            if not option in callOptions:
                value = self.valueGetFunc(option[0], option[1])
                self.log.debug('Adding unchanged option in section "%s" with name "%s" and value "%s" to changed options',
                               option[0], option[1], str(value))
                callOptions[option] = value
        
        
    def addCallback(self, options, func, funcArgs=[], funcKw={}, valueArgPlace=0, callType='value-funcArgSingle', optionTranslationTable={}, callWithAllOptions=False):
        #get id
        callbackId = self.nextCallbackId
        self.nextCallbackId += 1
        
        #add callback object
        self.callbackObjs[callbackId] = {'callback':ConfigCallback(options, func, funcArgs, funcKw, valueArgPlace, callType, optionTranslationTable),
                                         'options':options,
                                         'callWithAllOptions':callWithAllOptions}
                                         
        #add callback id to options
        for section, name in options:
            self.optionsToCallbackId[section][name].add(callbackId)
        return callbackId
        
        
    def removeCallback(self, callbackId):
        callbackSet = self.callbackObjs[callbackId]
        
        for section, name in callbackSet['options']:
            self.optionsToCallbackId[section][name].remove(callbackId)
            if len(self.optionsToCallbackId[section][name])==0:
                del self.optionsToCallbackId[section][name]
                
                if len(self.optionsToCallbackId[section])==0:
                    del self.optionsToCallbackId[section]
        
        del self.callbackObjs[callbackId]
        
        
    def execCallbacks(self, changedOptions):
        for option, value in changedOptions.iteritems():
            self.log.debug('Got changed option in section "%s" with name "%s" and new value "%s"',
                           option[0], option[1], value)
                        
        #build map
        callbackMapping = defaultdict(dict)
        for option, value in changedOptions.iteritems():
            if option[0] in self.optionsToCallbackId:
                #callbacks for this sections exist
                if option[1] in self.optionsToCallbackId[option[0]]:
                    #callbacks exist for this option
                    for callbackId in self.optionsToCallbackId[option[0]][option[1]]:
                        #add option
                        callbackMapping[callbackId][option] = value
                        
        #execute callbacks
        for callbackId, options in callbackMapping.iteritems():
            self.log.debug('Executing callback with ID %i', callbackId)
            callbackSet = self.callbackObjs[callbackId]
            if callbackSet['callWithAllOptions']:
                self._fillOptionDict(callbackSet['options'], options)
            callbackSet['callback'].call(options)
        
        
        
        
class ConfigCallback:
    def __init__(self, options, func, funcArgs=[], funcKw={}, valueArgPlace=0, callType='value-funcArgSingle', optionTranslationTable={}):
        self.options = options
        self.func = func
        self.funcArgs = funcArgs
        self.funcKw = funcKw
        self.valueArgPlace = valueArgPlace
        self.callType = callType
        self.optionTranslationTable = optionTranslationTable
        self.log = logging.getLogger('ConfigCallback')
        
    def _getSortedOptionValues(self, changedOptions):
        sortedValues = []
        for option in self.options:
            sortedValues.append(changedOptions[option])
        return sortedValues
        
        
    def _execFunction(self, func, funcArgs, funcKw):
        self.log.debug('Calling function "%s" with arguments "%s" and keywords "%s"',
                       str(func), str(funcArgs), str(funcKw))
        apply(func, funcArgs, funcKw)
        
        
    def call(self, changedOptions):
        for option, value in changedOptions.iteritems():
            self.log.debug('Got option in section "%s" with name "%s" and value "%s"',
                           option[0], option[1], value)
            assert option in self.options, 'Not in options list, why did we get called with this?!'

        if self.callType == 'value-funcArgSingle':
            #call callback with value of one changed option as argument
            for value in changedOptions.itervalues():
                funcArgs = self.funcArgs[:self.valueArgPlace] + [value] + self.funcArgs[self.valueArgPlace:]
                self._execFunction(self.func, funcArgs, self.funcKw)
                
        elif self.callType == 'value-funcArgAll':
            #call callback with values of all changed options as arguments
            funcArgs = self.funcArgs[:self.valueArgPlace] + self._getSortedOptionValues(changedOptions) + self.funcArgs[self.valueArgPlace:]
            self._execFunction(self.func, funcArgs, self.funcKw)
            
        elif self.callType == 'item-funcKwSingle':
            #call callback with value of one changed option as an additional keyword
            for option, value in changedOptions.iteritems():
                funcKw = self.funcKw.copy()
                option = self.optionTranslationTable.get(option, str(option[1]))
                funcKw[option] = value
                self._execFunction(self.func, self.funcArgs, funcKw)
            
        elif self.callType == 'item-funcKwAll':
            #call callback with values of all changed options as additional keywords
            funcKw = self.funcKw.copy()
            for option, value in changedOptions.iteritems():
                option = self.optionTranslationTable.get(option, str(option[1]))
                funcKw[option] = value
            self._execFunction(self.func, self.funcArgs, funcKw)
            
        elif self.callType == 'item-dictArg':
            #call callback with a dict of all changed options and their new values as an argument
            optionDict = {}
            for option, value in changedOptions.iteritems():
                option = self.optionTranslationTable.get(option, str(option[1]))
                optionDict[option] = value
            funcArgs = self.funcArgs[:self.valueArgPlace] + [optionDict] + self.funcArgs[self.valueArgPlace:]
            self._execFunction(self.func, funcArgs, self.funcKw)
            
        elif self.callType == 'item-listArg':
            #call callback with a list, which contains tuples with options-value pairs, as an argument
            itemList = list([(self.optionTranslationTable.get(option, str(option[1])), value) for option, value in changedOptions.iteritems()])
            funcArgs = self.funcArgs[:self.valueArgPlace] + [itemList] + self.funcArgs[self.valueArgPlace:]
            self._execFunction(self.func, funcArgs, self.funcKw)
