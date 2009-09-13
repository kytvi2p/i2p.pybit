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

from ConfigParser import SafeConfigParser

from collections import defaultdict
import logging
import os
import re
import threading

class Config:
    def __init__(self, configFile='config.conf', configDefaults={}):
        self.configFile = configFile
        
        self.log = logging.getLogger('Config')
        self.ipCheck = re.compile('^((25[0-5])|(2[0-4][0-9])|([1]??[1-9]??[0-9]))(.((25[0-5])|(2[0-4][0-9])|([1]??[1-9]??[0-9]))){3,3}$')
        self.config = SafeConfigParser()
        
        #create config file if it doesn't exist
        if os.path.isfile(self.configFile)==False:
            self.log.warn("Didn't find a config file, creating one.")
            try:
                merk = open(self.configFile, 'wb')
                merk.close()
            except:
                self.log.warn("Failed to create config file!")
            
        #read config file
        self.config.read(self.configFile)
        
        #set internal structures
        self.callbacks = defaultdict(lambda: defaultdict(lambda: {'nextCallbackId':0, 'callbacks':{}}))
        self.configDefaults = defaultdict(dict)
        self._addDefaults(configDefaults)
        self._setDefaults(self.configDefaults)
        
        #write config
        self._writeConfig()
        
        #main lock
        self.lock = threading.RLock()
        
        
    ##internal functions
    
    def _writeConfig(self):
        #write config
        self.log.debug("Trying to write options back to config file")
        try:
            merk = open(self.configFile, 'wb')
            self.config.write(merk)
            merk.close()
        except:
            self.log.warn("Failed to write to config file!")
            
    
    def _addDefaults(self, configDefaults):
        for section in configDefaults.iterkeys():
            for option, value in configDefaults[section].iteritems():
                self.configDefaults[section][option] = value
                
    
    def _setDefaults(self, configDefaults):
        #set default options if not already set
        for section in configDefaults.iterkeys():
            if not self.config.has_section(section):
                #section doesn't exist, create it
                self.config.add_section(section)
                
            for option in configDefaults[section].iterkeys():
                if not self.config.has_option(section, option):
                    #option isn't known, add it
                    self.config.set(section, option, str(configDefaults[section][option][0]))
                elif not self._checkOptionType(section, option, configDefaults[section][option][0], configDefaults[section][option][1]):
                    #options exists but has the wrong type, replace it
                    self.config.set(section, option, str(configDefaults[section][option][0]))
    
    
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
    
    
    def _addCallbackForOption(self, section, option, func, funcArgs, funcKw):
        #callbacks exist for this option
        optionSet = self.callbacks[section][option]
        callbackId = optionSet['nextCallbackId']
        optionSet['nextCallbackId'] += 1
        
        optionSet['callbacks'][callbackId] = {'func':callback,
                                              'funcArgs':callbackArgs,
                                              'funcKw':callbackKw}
        return callbackId
                                                        
    
    def _execAllCallbacksForOption(self, section, option, value):
        if section in self.callbacks:
            #section exists
            if option in self.callbacks[section]:
                #there exist callbacks for this option
                for callback in self.callbacks:
                    apply(callback['func'], [value]+callback['funcArgs'], callback['funcKw'])
                    
                    
    def _removeCallbackForOption(self, section, option, callbackId):
        del self.callbacks[section][option][callbackId]
        
        
    def _removeAllCallbacksForOption(self, section, option):
        if section in self.callbacks:
            #section exists
            if option in self.callbacks[section]:
                #there exist callbacks for this option
                self.callbacks[section][option]['callbacks'].clear()
                

    ##external functions - defaults
    
    def addDefaults(self, configDefaults):
        self.lock.acquire()
        self._addDefaults(configDefaults)
        self._setDefaults(configDefaults)
        self.lock.release()
        
        
    ##external functions - callbacks
    
    def addCallbackForOption(self, section, option, func, funcArgs=[], funcKw={}):
        self.lock.acquire()
        callbackId = self._addCallbackForOption(section, option, func, funcArgs, funcKw)
        self.lock.release()
        return callbackId
    
    
    def removeCallbackForOption(self, section, option, callbackId):
        self.lock.acquire()
        self._removeCallbackForOption(section, option, callbackId)
        self.lock.release()
        
        
    def removeAllCallbacksForOption(self, section, option):
        self.lock.acquire()
        self._removeAllCallbacksForOption(section, option)
        self.lock.release()
        
    
    ##external functions - sections
    
    def addSection(self, section):
        self.lock.acquire()
        self.config.addSection(section)
        merk = open(self.configFile, 'wb')
        self.config.write(merk)
        merk.close()
        self.lock.release()
        
        
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

    def get(self, section, option):
        self.lock.acquire()
        if not self.config.has_option(section, option):
            result = None
        else:
            result = self.config.get(section, option)
        self.lock.release()
        return result
    

    def getInt(self, section, option):
        self.lock.acquire()
        if not self.config.has_option(section, option):
            result = None
        else:
            result = self.config.get(section, option)
            try:
                result = int(result)
            except:
                result = None
        self.lock.release()
        return result
    

    def getBool(self, section, option):
        self.lock.acquire()
        if not self.config.has_option(section, option):
            result = None
        else:
            result = self.config.get(section, option)
            try:
                result = result.lower() == 'true'
            except:
                result = None
        self.lock.release()
        return result
    

    def getFloat(self, section, option):
        self.lock.acquire()
        if not self.config.has_option(section, option):
            result = None
        else:
            result = self.config.get(section, option)
            try:
                result = float(result)
            except:
                result = None
        self.lock.release()
        return result
    

    def set(self, section, option, value):
        #set value
        self.lock.acquire()
        failureMsg = None
        if not self._checkOptionType(section, option, value, self._getOptionType(section, option)):
            failureMsg = 'invalid type'
        else:
            self._execAllCallbacksForOption(section, option, value)
            self.config.set(section, option, str(value))
            
            #write changed values to config file
            self.log.debug("Trying to write possibly modified options back to config file")
            try:
                merk = open(self.configFile, 'wb')
                self.config.write(merk)
                merk.close()
            except:
                self.log.warn("Failed to write to config file!")
        self.lock.release()
        return failureMsg
