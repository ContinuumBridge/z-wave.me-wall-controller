#!/usr/bin/env python
# adaptor_a.py
# Copyright (C) ContinuumBridge Limited, 2014 - All Rights Reserved
# Written by Peter Claydon
#
ModuleName               = "zwave.me_wall_controller"
BATTERY_CHECK_INTERVAL   = 21600    # How often to check battery (secs) = 6 hours
CHECK_ALIVE_INTERVAL     = 10800    # How often to check if device is alive

import sys
import time
import os
from pprint import pprint
from cbcommslib import CbAdaptor
from cbconfig import *
from twisted.internet import threads
from twisted.internet import reactor

class Adaptor(CbAdaptor):
    def __init__(self, argv):
        self.status =           "ok"
        self.state =            "stopped"
        self.apps =             {"number_buttons": [],
                                 "battery": [],
                                 "connected": []}
        self.currentValue =     "0"
        self.lastWakeupTime =   time.time()
        # super's __init__ must be called:
        #super(Adaptor, self).__init__(argv)
        CbAdaptor.__init__(self, argv)
 
    def setState(self, action):
        # error is only ever set from the running state, so set back to running if error is cleared
        if action == "error":
            self.state == "error"
        elif action == "clear_error":
            self.state = "running"
        msg = {"id": self.id,
               "status": "state",
               "state": self.state}
        self.sendManagerMessage(msg)

    def sendCharacteristic(self, characteristic, data, timeStamp):
        msg = {"id": self.id,
               "content": "characteristic",
               "characteristic": characteristic,
               "data": data,
               "timeStamp": timeStamp}
        for a in self.apps[characteristic]:
            self.sendMessage(msg, a)

    def checkBattery(self):
        cmd = {"id": self.id,
               "request": "post",
               "address": self.addr,
               "instance": "0",
               "commandClass": "128",
               "action": "Get",
               "value": ""
              }
        self.sendZwaveMessage(cmd)
        reactor.callLater(BATTERY_CHECK_INTERVAL, self.checkBattery)

    def checkConnected(self):
        if time.time() - self.updateTime > CHECK_ALIVE_INTERVAL + 60:
            self.connected = False
        else:
            self.connected = True
        self.sendCharacteristic("connected", self.connected, time.time())
        self.lastUpdateTime = self.updateTime
        reactor.callLater(CHECK_ALIVE_INTERVAL, self.checkConnected)

    def onZwaveMessage(self, message):
        #self.cbLog("debug", "onZwaveMessage, message: " + str(message))
        if message["content"] == "init":
            self.updateTime = 0
            self.lastUpdateTime = time.time()
            # number_buttons 
            cmd = {"id": self.id,
                   "request": "get",
                   "address": self.addr,
                   "instance": "0",
                   "commandClass": "91",
                   "value": "currentScene"
                  }
            self.sendZwaveMessage(cmd)
            # Battery
            cmd = {"id": self.id,
                   "request": "get",
                   "address": self.addr,
                   "instance": "0",
                   "commandClass": "128"
                  }
            self.sendZwaveMessage(cmd)
            reactor.callLater(60, self.checkBattery)
            # wakeup 
            cmd = {"id": self.id,
                   "request": "get",
                   "address": self.addr,
                   "instance": "0",
                   "commandClass": "132",
                   "value": "lastWakeup"
                  }
            self.sendZwaveMessage(cmd)
            reactor.callLater(CHECK_ALIVE_INTERVAL, self.checkConnected)
        elif message["content"] == "data":
            try:
                if message["commandClass"] == "91":
                    if message["value"] == "currentScene":
                        value = message["data"]["value"]
                        updateTime = message["data"]["updateTime"]
                        if value == 1:
                            data = {"1": "on"}
                        elif value == 2:
                            data = {"2": "on"}
                        elif value == 5:
                            data = {"3": "on"}
                        elif value == 6:
                            data = {"4": "on"}
                        else:
                            data = {"0": "off"}
                        self.cbLog("debug", "onZwaveMessage, value: " + str(value))
                        self.sendCharacteristic("number_buttons", data, updateTime)
                elif message["commandClass"] == "128":
                     battery = message["data"]["last"]["value"] 
                     self.cbLog("debug", "onZwaveMessage, battery: " + str(battery))
                     msg = {"id": self.id,
                            "status": "battery_level",
                            "battery_level": battery}
                     self.sendManagerMessage(msg)
                     self.sendCharacteristic("battery", battery, time.time())
                elif message["commandClass"] == "132":
                     self.cbLog("debug", "device woke up")
                else:
                    self.cbLog("warning", "onZwaveMessage. Unrecognised message: " + str(message))
                self.updateTime = message["data"]["updateTime"]
            except Exception as ex:
                self.cbLog("warning", "Exception: " + str(message) + str(type(ex)) + str(ex.args))
    def onAppInit(self, message):
        self.cbLog("debug", "onAppInit, message: " + str(message))
        resp = {"name": self.name,
                "id": self.id,
                "status": "ok",
                "service": [{"characteristic": "number_buttons", "interval": 0},
                            {"characteristic": "battery", "interval": 600},
                            {"characteristic": "connected", "interval": 600}],
                "content": "service"}
        self.sendMessage(resp, message["id"])
        self.setState("running")

    def onAppRequest(self, message):
        # Switch off anything that already exists for this app
        for a in self.apps:
            if message["id"] in self.apps[a]:
                self.apps[a].remove(message["id"])
        # Now update details based on the message
        for f in message["service"]:
            if message["id"] not in self.apps[f["characteristic"]]:
                self.apps[f["characteristic"]].append(message["id"])
        self.cbLog("debug", "apps: " + str(self.apps))

    def onAppCommand(self, message):
        if "data" not in message:
            self.cbLog("warning", "app message without data: " + str(message))
        else:
            self.cbLog("warning", "This is a sensor. Message not understood: " +  str(message))

    def onConfigureMessage(self, config):
        """Config is based on what apps are to be connected.
            May be called again if there is a new configuration, which
            could be because a new app has been added.
        """
        self.setState("starting")

if __name__ == '__main__':
    Adaptor(sys.argv)
