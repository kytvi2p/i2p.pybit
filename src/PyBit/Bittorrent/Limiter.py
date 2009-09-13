"""
Copyright 2009  Blub

Different classes for distributing available ressources in a fair way.
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

from collections import defaultdict
from copy import copy
from random import sample
import threading


class RefillingQuotaLimiter:
    def __init__(self, rate, interval=1, minQuota=1, maxQuotaRaise=100, maxQuotaReduce=100):
        self.rate = int(rate*interval)
        self.interval = int(interval)
        
        self.quota = self.rate
        self.minQuota = int(minQuota)
        self.maxQuotaRaise = maxQuotaRaise / 100.0
        self.maxQuotaReduce = maxQuotaReduce / 100.0
        
        self.usedUnits = 0
        self.users = {}        
        
        self.limited = False
        self.anyLimiting = False
        self.lock = threading.Lock()
        
        
    def changeRate(self, newRate):
        self.lock.acquire()
        self.quota = max(int((self.quota/(self.rate*1.0))*newRate*self.interval) ,self.minQuota)
        self.rate = int(newRate*self.interval)
        assert self.quota >= self.minQuota, 'too low?!'
        assert self.quota <= self.rate, 'too high?!'
        self.lock.release()
        
        
    def addUser(self, ident, callback=None, callbackArgs=[], callbackKw={}):
        self.lock.acquire()
        assert not ident in self.users,'Tried to add user twice'
        self.users[ident]={'usedUnits':0,
                           'limited':False,
                           'callback':callback,
                           'callbackArgs':callbackArgs,
                           'callbackKw':callbackKw}
        self.lock.release()
        
        
    def removeUser(self, ident):
        self.lock.acquire()
        del self.users[ident]
        self.lock.release()
        
        
    def refill(self):
        self.lock.acquire()
        if len(self.users)>0:
            
            if self.usedUnits >= self.rate:
                #we hit the roof so to speak
                self.limited = True
            else:
                self.limited = False
                
            quotaLimitedUsers = 0 #users limited due to their Quota
            rateLimitedUsers = 0 #users limited due to the max rate
            unitsUsedByOther = 0
            
            self.anyLimiting = False
            for user in self.users.itervalues():
                if user['limited']:
                    self.anyLimiting = True
                    if user['usedUnits'] < self.quota:
                        #limited due to the max rate
                        rateLimitedUsers += 1
                    else:
                        #limited due to Quota
                        quotaLimitedUsers += 1
                        
                    user['limited'] = False
                    if user['callback'] is not None:
                        apply(user['callback'], [True]+user['callbackArgs'], user['callbackKw'])
                    
                else:
                    unitsUsedByOther += user['usedUnits']
                    
                user['usedUnits']=0
                
            if quotaLimitedUsers > 0 and self.limited == False:
                #we have a too low quota
                unusedUnits = self.rate - self.usedUnits
                self.quota += max(min((unusedUnits/quotaLimitedUsers), int(self.quota*self.maxQuotaRaise)), 1)
                
            elif rateLimitedUsers > 0:
                #we have a too high quota
                newQuota = (self.rate - unitsUsedByOther)/(quotaLimitedUsers + rateLimitedUsers)
                self.quota -= max(int(self.quota*self.maxQuotaReduce), 1)
                if newQuota > self.quota:
                    self.quota = newQuota
                if self.quota < self.minQuota:
                    self.quota = self.minQuota
                    
            self.usedUnits = 0
        self.lock.release()
        
        
    def claimUnits(self, ident, wantedUnits=None):
        self.lock.acquire()
        if wantedUnits is None:
            wantedUnits = self.rate
            
        #determine how much may be used
        user = self.users[ident]
        usedQuota = min(self.rate - self.usedUnits, self.quota - user['usedUnits'], wantedUnits)
        
        #add used units
        user['usedUnits'] += usedQuota
        self.usedUnits += usedQuota
        
        #check if we got limited
        if usedQuota < wantedUnits:
            user['limited'] = True
            if user['callback'] is not None:
                apply(user['callback'], [False]+user['callbackArgs'], user['callbackKw'])
        
        self.lock.release()
        return usedQuota
        
        
    def hasLimited(self):
        self.lock.acquire()
        limited = self.limited
        self.lock.release()
        return limited
        
        
    def hasLimitedAnything(self):
        self.lock.acquire()
        anyLimiting = self.anyLimiting
        self.lock.release()
        
        
        
        
class SelfRefillingQuotaLimiter(RefillingQuotaLimiter):
    def __init__(self, scheduler, rate, interval=1, maxQuotaRaise=100, maxQuotaReduce=100):
        RefillingQuotaLimiter.__init__(self, rate, interval, maxQuotaRaise, maxQuotaReduce)
        
        self.sched = scheduler
        self.eventId = self.sched.scheduleEvent(self.refill, timedelta=0, repeatdelta=self.interval)
        
        
    def stop(self, clearAll=True):
        self.lock.acquire()
        if self.eventId is not None:
            self.sched.removeEvent(self.eventId)
            self.eventId = None
            if clearAll:
                self.quota = self.rate
                self.usedUnits = 0
                self.users = {}                
                self.limited = False
                self.anyLimiting = False
        self.lock.release()
        
        
    def start(self):
        self.lock.acquire()
        self.eventId = self.sched.scheduleEvent(self.recalculateQuota, timedelta=0, repeatdelta=self.interval)
        self.lock.release()
        
        
        
        
class ExactRefillingQuotaLimiter:
    def __init__(self, rate, interval=1, minQuota=1, maxQuotaRaise=100, maxQuotaReduce=100):
        self.rate = int(rate*interval)
        self.interval = int(interval)
        
        self.randomUnits = 0
        self.quota = self.rate
        self.minQuota = int(minQuota)
        self.maxQuotaRaise = maxQuotaRaise / 100.0
        self.maxQuotaReduce = maxQuotaReduce / 100.0
        
        self.usedUnits = 0
        self.users = {}        
        
        self.limited = False
        self.anyLimiting = False
        self.lock = threading.Lock()
        
        
    def changeRate(self, newRate):
        self.lock.acquire()
        self.quota = max(int((self.quota/(self.rate*1.0))*newRate*self.interval) ,self.minQuota)
        self.randomUnits = 0
        self.rate = int(newRate*self.interval)
        assert self.quota >= self.minQuota, 'too low?!'
        assert self.quota <= self.rate, 'too high?!'
        self.lock.release()
        
        
    def addUser(self, ident, callback=None, callbackArgs=[], callbackKw={}):
        self.lock.acquire()
        assert not ident in self.users,'Tried to add user twice'
        self.users[ident]={'usedUnits':0,
                           'quota':self.quota,
                           'limited':False,
                           'callback':callback,
                           'callbackArgs':callbackArgs,
                           'callbackKw':callbackKw}
        self.lock.release()
        
        
    def removeUser(self, ident):
        self.lock.acquire()
        del self.users[ident]
        self.lock.release()
        
        
    def refill(self):
        self.lock.acquire()
        if len(self.users) > 0:
            
            if self.usedUnits >= self.rate:
                self.limited = True
            else:
                self.limited = False
            
            limitedUsersList = []
            quotaLimitedUsers = 0 #users limited due to their Quota
            rateLimitedUsers = 0 #users limited due to the max rate
            notLimitedUsers = 0 #users not limited
            unitsUsedByOther = 0
            
            self.anyLimiting = False
            for user in self.users.itervalues():
                if user['limited']:
                    self.anyLimiting = True
                    limitedUsersList.append(user)
                    if user['usedUnits'] < user['quota']:
                        #limited due to the max rate
                        rateLimitedUsers += 1
                    else:
                        #limited due to quota
                        quotaLimitedUsers += 1
                        
                    user['limited'] = False
                    if user['callback'] is not None:
                        apply(user['callback'], [True]+user['callbackArgs'], user['callbackKw'])
                    
                else:
                    notLimitedUsers += 1
                    unitsUsedByOther += user['usedUnits']
                    
                user['usedUnits']=0
                
            if quotaLimitedUsers > 0 and not self.limited:
                #we have a too low quota
                unusedUnits = self.rate - (self.usedUnits - self.randomUnits)
                quotaIncrease = unusedUnits / quotaLimitedUsers
                maxQuotaIncrease = self.quota * self.maxQuotaRaise
                if quotaIncrease > maxQuotaIncrease:
                    self.quota += maxQuotaIncrease
                    self.randomUnits = 0
                else:
                    self.quota += quotaIncrease
                    self.randomUnits = unusedUnits % quotaLimitedUsers
                
            elif rateLimitedUsers > 0:
                #we have a too high quota
                self.randomUnits = (self.rate - unitsUsedByOther) % (quotaLimitedUsers + rateLimitedUsers)
                relativeMinQuota = self.quota - max(int(self.quota * self.maxQuotaReduce), 1)
                calcQuota = (self.rate - unitsUsedByOther) / (quotaLimitedUsers + rateLimitedUsers)
                self.quota = max(relativeMinQuota, calcQuota)
                
                if self.quota < self.minQuota:
                    self.quota = self.minQuota
                    self.randomUnits = 0
                    
            elif quotaLimitedUsers < self.randomUnits:
                #bandwidth demand dropped
                self.randomUnits = quotaLimitedUsers
                        
            assert self.randomUnits <= (quotaLimitedUsers + rateLimitedUsers), 'Too many random units! RandomUnits %i, QuotaLimitedUsers %i and RateLimitedUsers %i' % (self.randomUnits, quotaLimitedUsers, rateLimitedUsers)
            
            #set new quota
            for user in self.users.itervalues():
                user['quota'] = self.quota
                
            #use random units
            choosenUsers = sample(limitedUsersList, self.randomUnits)
            for user in choosenUsers:
                user['quota'] += 1
                    
        self.usedUnits = 0
        self.lock.release()
        
        
    def claimUnits(self, ident, wantedUnits=None):
        self.lock.acquire()
        if wantedUnits is None:
            wantedUnits = self.rate
            
        #determine how much may be used
        user = self.users[ident]
        usedQuota = min(self.rate - self.usedUnits, user['quota'] - user['usedUnits'], wantedUnits)
        
        #add used units
        user['usedUnits'] += usedQuota
        self.usedUnits += usedQuota
        
        #check if we got limited
        if usedQuota < wantedUnits:
            user['limited'] = True
            if user['callback'] is not None:
                apply(user['callback'], [False]+user['callbackArgs'], user['callbackKw'])
        
        self.lock.release()
        return usedQuota
        
        
    def hasLimited(self):
        self.lock.acquire()
        limited = self.limited
        self.lock.release()
        return limited
        
        
    def hasLimitedAnything(self):
        self.lock.acquire()
        anyLimiting = self.anyLimiting
        self.lock.release()
        
        
    def getRate(self):
        self.lock.acquire()
        rate = self.rate
        self.lock.release()
        return rate
    
    
    def getQuota(self):
        self.lock.acquire()
        quota = self.quota
        self.lock.release()
        return quota
    
    
    def getRandomUnits(self):
        self.lock.acquire()
        randomUnits = self.randomUnits
        self.lock.release()
        return randomUnits
        
        
        
class ManualQuotaLimiter:
    def __init__(self, limit):
        self.limit = int(limit)
        self.quotaPrioList = []
        self.lock = threading.Lock()
        
        
    def changeLimit(self, newLimit):
        self.lock.acquire()
        self.limit = int(newLimit)
        self.lock.release()
        
        
    def addUser(self, ident):
        self.lock.acquire()
        self.quotaPrioList.append(ident)
        self.lock.release()
        
        
    def removeUser(self, ident):
        self.lock.acquire()
        self.quotaPrioList.remove(ident)
        self.lock.release()
        
        
    def getQuotas(self, users):
        #gets a list of (neededUnits, users) tuples and returns a users=>givenUnits defaultdict (defaulting to zero)
        self.lock.acquire()
        
        #init
        users = copy(users)
        unusedUnits = self.limit
        allocatedUnits = defaultdict(int)
        unsatisfiedUsers = set()
        
        #try to assign units normally
        quota = unusedUnits / max(len(users), 1)
        users.sort()
        idx = 0
        while idx < len(users):
            wantedUnits, user = users[idx]
            idx += 1
            
            #allocate units
            allowedUnits = min(wantedUnits, quota)
            allocatedUnits[user] = allowedUnits
            unusedUnits -= allowedUnits
            
            #check if demand was met
            if wantedUnits <= quota and (not idx == len(users)):
                quota = unusedUnits / (len(users) - idx)
                
            elif wantedUnits > quota:
                unsatisfiedUsers.add(user)
                
                
        if unusedUnits > 0 and len(unsatisfiedUsers) > 0:
            #assign the remaining units by round-robin
            assert unusedUnits < len(unsatisfiedUsers), 'more then one unit left per unsatisfied user?!'
            idx = 0
            while unusedUnits > 0:
                user = self.quotaPrioList[idx]
                idx += 1
                if user in unsatisfiedUsers:
                    allocatedUnits[user] += 1
                    unusedUnits -= 1
                    
            self.quotaPrioList = self.quotaPrioList[idx:] + self.quotaPrioList[:idx]
        
        self.lock.release()
        return allocatedUnits
    
    
    def getLimit(self):
        self.lock.acquire()
        limit = self.limit
        self.lock.release()
        return limit
                
                
                    
        
        
        
        
#class StaticQuotaLimiter:
#    def __init__(self, limit, minQuota=1, maxQuotaRaise=100, maxQuotaReduce=100):
#        self.limit = int(limit)
#        
#        self.fixedQuota = self.limit
#        self.randomQuota = 0
#        self.minQuota = int(minQuota)
#        self.maxQuotaRaise = maxQuotaRaise / 100.0
#        self.maxQuotaReduce = maxQuotaReduce / 100.0
#        
#        self.usedUnits = 0
#        self.users = {}
#        self.userList = []
#        
#        self.limited = False
#        self.anyLimiting = False
#        self.lock = threading.Lock()
#        
#        
#    def changeLimit(self, newLimit):
#        self.lock.acquire()
#        self.fixedQuota = max(int((self.fixedQuota/(self.limit*1.0))*newLimit) ,self.minQuota)
#        self.randomQuota = 0
#        self.limit = int(newLimit)
#        assert self.fixedQuota >= self.minQuota, 'too low?!'
#        assert self.fixedQuota <= self.limit, 'too high?!'
#        self.lock.release()
#        
#        
#    def addUser(self, ident, callback=None, callbackArgs=[], callbackKw={}):
#        self.lock.acquire()
#        assert not ident in self.users,'Tried to add user twice'
#        self.users[ident]={'usedUnits':0,
#                           'quota':self.fixedQuota,
#                           'limited':False,
#                           'callback':callback,
#                           'callbackArgs':callbackArgs,
#                           'callbackKw':callbackKw}
#        self.userList.append(ident)
#        self.lock.release()
#        
#        
#    def removeUser(self, ident):
#        self.lock.acquire()
#        del self.users[ident]
#        self.userList.remove(ident)
#        self.lock.release()
#        
#        
#    def recalculateQuota(self):
#        self.lock.acquire()
#        if len(self.users)>0:
#            
#            if self.usedUnits >= self.limit:
#                self.limited = True
#            else:
#                self.limited = False
#                
#            quotaLimitedUsers = 0 #users limited due to their Quota
#            globalLimitedUsers = 0 #users limited due to the max limit
#            unitsUsedByOther = 0
#            
#            self.anyLimiting = False
#            for user in self.users.itervalues():
#                if user['limited']:
#                    self.anyLimiting = True
#                    if user['usedUnits'] < self.quota:
#                        #limited due to the max limit
#                        globalLimitedUsers += 1
#                    else:
#                        #limited due to Quota
#                        quotaLimitedUsers += 1
#                        
#                    user['limited'] = False
#                    if user['callback'] is not None:
#                        apply(user['callback'], [True]+user['callbackArgs'], user['callbackKw'])
#                    
#                else:
#                    unitsUsedByOther += user['usedUnits']
#                
#            if quotaLimitedUsers > 0 and self.limited == False:
#                #we have a too low quota
#                unusedUnits = self.limit - self.usedUnits
#                self.quota += max(min((unusedUnits/quotaLimitedUsers), int(self.quota*self.maxQuotaRaise)), 1)
#                
#            elif globalLimitedUsers > 0:
#                #we have a too high quota
#                newQuota = (self.limit - unitsUsedByOther)/(quotaLimitedUsers + globalLimitedUsers)
#                self.quota -= max(int(self.quota*self.maxQuotaReduce), 1)
#                if newQuota > self.quota:
#                    self.quota = newQuota
#                if self.quota < self.minQuota:
#                    self.quota = self.minQuota
#                    
#        self.lock.release()
#        
#        
#    def claimUnits(self, ident, wantedUnits=None):
#        self.lock.acquire()
#        if wantedUnits is None:
#            wantedUnits = self.limit
#            
#        #determine how much may be used
#        user = self.users[ident]
#        usedQuota = min(self.limit - self.usedUnits, self.quota - user['usedUnits'], wantedUnits)
#        
#        #add used units
#        user['usedUnits'] += usedQuota
#        self.usedUnits += usedQuota
#        
#        #check if we got limited
#        if usedQuota < wantedUnits:
#            user['limited'] = True
#            if user['callback'] is not None:
#                apply(user['callback'], [False]+user['callbackArgs'], user['callbackKw'])
#                
#        self.lock.release()
#        return spendQuota
#        
#        
#    def releaseUnits(self, ident, units):
#        self.lock.acquire()
#        
#        user = self.users[ident]        
#        assert user['usedUnits'] >= units,'Releasing units which were never claimed?!'
#        
#        user['usedUnits'] -= units
#        self.usedUnits -= units
#        
#        if user['limited'] and user['usedUnits'] <= self.quota and self.usedUnits <= self.limit:
#            #were limited but are now below the limit (or match it)
#            user['limited'] = False
#            if user['callback'] is not None:
#                apply(user['callback'], [True]+user['callbackArgs'], user['callbackKw'])
#            
#        self.lock.release()
#        
#        
#    def hasLimited(self):
#        self.lock.acquire()
#        limited = self.limited
#        self.lock.release()
#        return limited
#        
#        
#    def hasLimitedAnything(self):
#        self.lock.acquire()
#        anyLimiting = self.anyLimiting
#        self.lock.release()
