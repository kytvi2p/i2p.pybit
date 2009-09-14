"""
Copyright 2009  Blub

LogController.py, a class for managing logging building upon the "logging" facility.
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

import logging
import logging.handlers
import threading


class LogController:
    def __init__(self, logHandler):
        """
        logHandler is a list of tuples with the following format:
            (*identifier*, *type*, *options*)
        
        
        *identifier* should be a string and can be used to later change for example the
        loglevel of this log handler.
        
        
        *type* determines the type of log handler and must be one of the following:
            fileLog | consoleLog
        
        
        *options* is a dict with the options for this log handler, the available
        options depend on the type of the log handler. The available ones are:
            
            Options for type "consoleLog":
                logLevel = debug | info | warning | error | critical
                    threshold for log messages which should be written to the console, defaults
                    to "debug". "debug" will also be used if anything else then these five loglevels
                    is given.
                    
                logFormat = *formatString*
                    *formatString* will be directly passed to the "logging" module as the format string
                    and thus has to fulfill the requirements of the "logging" module.
            
            
            Options for type "fileLog": 
                filename = *string*
                    name of the logfile, defaults to "log"
                    
                logLevel = debug | info | warning | error | critical
                    threshold for log messages which should be written to the logfile, defaults
                    to "debug". "debug" will also be used if anything else then these five loglevels
                    is given.
                    
                logFormat = *formatString*
                    *formatString* will be directly passed to the "logging" module as the format string
                    and thus has to fulfill the requirements of the "logging" module.
                    
                fileMaxBytes = *number*
                    if set, causes the log file to be 'rotated' once it reaches this size (in bytes)
                    
                fileMaxRotatedCount = *number*
                    determines how many old ('rotated') logs will be kept, defaults to 0
                    
        """
        
        #setup root logger
        self.rootLogger = logging.getLogger('')
        self.rootLogger.setLevel(logging.DEBUG)
        
        #setup handler
        self.handler = {}
        for identifier, handlerType, options in logHandler:
           self._addHandler(identifier, handlerType, options)
        
        self.lock = threading.Lock()
        
    
    ##internal functions - loglevel
        
    def _translateLoglevel(self, loglevel):
        loglevel = loglevel.lower()
        
        realLoglevel = logging.DEBUG
        if loglevel=='critical':
            realLoglevel = logging.CRITICAL
        elif loglevel=='error':
            realLoglevel = logging.ERROR
        elif loglevel=='warning':
            realLoglevel = logging.WARNING
        elif loglevel=='info':
            realLoglevel = logging.INFO
        return realLoglevel
    
    
    def _setHandlerLoglevel(self, identifier, loglevel):
        self.handler[identifier]['handler'].setLevel(self._translateLoglevel(loglevel))
        
        
    ##internal functions - handler
    
    def _createConsoleLogHandler(self, identifier, options):
        loglevel = self._translateLoglevel(options.get('logLevel', 'debug'))
        logformat = options.get('logFormat')
        
        #create handler
        handler = logging.StreamHandler()
        
        #set loglevel
        handler.setLevel(loglevel)
        
        #set formatter if necessary
        if logformat is not None:
            formatter = logging.Formatter(logformat)
            handler.setFormatter(formatter)
        return handler
        
        
    def _createFileLogHandler(self, identifier, options):
        filename = options.get('filename', 'log')
        loglevel = self._translateLoglevel(options.get('logLevel', 'debug'))
        logformat = options.get('logFormat')
        maxBytes = options.get('fileMaxBytes', 0)
        rotatedCount = options.get('fileMaxRotatedCount', 0)
        
        #create handler
        handler = logging.handlers.RotatingFileHandler(filename, maxBytes=maxBytes, backupCount=rotatedCount)
        
        #set loglevel
        handler.setLevel(loglevel)
        
        #set formatter if necessary
        if logformat is not None:
            formatter = logging.Formatter(logformat)
            handler.setFormatter(formatter)
        return handler
    
    
    def _addHandler(self, identifier, handlerType, options):
        if handlerType == 'consoleLog':
            handler = self._createConsoleLogHandler(identifier, options)
            
        elif handlerType == 'fileLog':
            handler = self._createFileLogHandler(identifier, options)
            
        else:
            handler = None
            
        if handler is not None:
            #add to root logger
            self.rootLogger.addHandler(handler)
                
            #add to dict
            self.handler[identifier] = {'handler':handler,
                                        'type':handlerType,
                                        'options':options}
                                        
                                        
    def _removeHandler(self, identifier):
        self.rootLogger.removeHandler(self.handler[identifier]['handler'])
        del self.handler[identifier]
                                            
                                            
    def _changeHandlerOptions(self, identifier, options):
        handlerType = self.handler[identifier]['type']
        self._removeHandler(identifier)
        self._addHandler(identifier, handlerType, options)
        
        
    def _changeHandlerOption(self, identifier, option, value):
        options = self.handler[identifier][options].copy()
        options[option] = value
        self._changeHandlerOptions(identifier, options)
                
                
    ##external functions - handler
    
    def addHandler(self, identifier, handlerType, options):
        self.lock.acquire()
        self._addHandler(identifier, handlerType, options)
        self.lock.release()
        
        
    def changeHandlerOption(self, identifier, option, value):
        self.lock.acquire()
        self._changeHandlerOption(identifier, option, value)
        self.lock.release()
        
    
    def changeHandlerOptions(self, identifier, options):
        self.lock.acquire()
        self._changeHandlerOptions(identifier, options)
        self.lock.release()
    
    
    def changeHandlerLoglevel(self, identifier, loglevel):
        self.lock.acquire()
        self._setHandlerLoglevel(identifier, loglevel)
        self.lock.release()
        
        
    def removeHandler(self, identifier):
        self.lock.acquire()
        self._removeHandler(identifier)
        self.lock.release()
        
    
    ##external functions - other
        
    def shutdown(self):
        self.lock.acquire()
        logging.shutdown()
        self.lock.release()