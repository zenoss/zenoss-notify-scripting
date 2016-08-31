#!/usr/bin/env python

import __main__
import curses
import logging
import os
import sys
import traceback
import time
import yaml
from api import ZAPI
from optparse import OptionParser
from random import randint
from random import random
import socket
from time import gmtime, strftime
import urllib2
if sys.platform.lower().startswith('linux'):
    import glib
    import gobject
    import thread
    from sound import playSound

# Setup app_path
app_path = os.path.dirname(os.path.abspath(getattr(__main__,'__file__','__main__.py')))

VERSION = 0.2

TIMESTAMP_ROW = 0
NAME_ROW = 1
ALERTS_ROW = 2

severities = [5]
event_states = [0]
production_states = [1000]
device_classes = '/Network*'
cycle_time = 15
username = 'username'
password = 'password'
sound_file = app_path + '/console-beep.mp3'
instances = [{"name": "Localhost", "short_name": "Lo", "target_instance": "http://localhost:8080"}]


# Option Parser
parser = OptionParser()
parser.add_option('-c', '--config-file', dest='config_file', help='Configuration file')
(options, args) = parser.parse_args()

# Use configuration file specified on commandline, if given
if options.config_file:
    config_file_options = yaml.load(open(options.config_file))
    if config_file_options.has_key('severities'): severities = config_file_options['severities']
    if config_file_options.has_key('event_states'): event_states = config_file_options['event_states']
    if config_file_options.has_key('production_states'): production_states = config_file_options['production_states']
    if config_file_options.has_key('device_classes'): device_classes = config_file_options['device_classes']
    if config_file_options.has_key('cycle_time'): cycle_time = config_file_options['cycle_time']
    if config_file_options.has_key('username'): username = config_file_options['username']
    if config_file_options.has_key('password'): password = config_file_options['password']
    if config_file_options.has_key('sound_file'): sound_file = app_path + "/" + config_file_options['sound_file']
    if config_file_options.has_key('instances'): instances = config_file_options['instances']


# Setup Logging and SysLogger
levels = {
    'debug':    logging.DEBUG,
    'info':     logging.INFO,
    'warning':  logging.WARNING,
    'error':    logging.ERROR,
    'critical': logging.CRITICAL
}

logName = app_path + "/logs/zenoss_beeps.log"
level = levels.get('debug', logging.NOTSET)
logging.basicConfig(filename=logName, level=level)

ZenBeep = logging.getLogger('ZenBeep')
ZenBeep.setLevel(logging.DEBUG)

class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'

    def disable(self):
        self.HEADER = ''
        self.OKBLUE = ''
        self.OKGREEN = ''
        self.WARNING = ''
        self.FAIL = ''
        self.ENDC = ''

# Method for Playback
def play_sound(sound_file):
    if sys.platform.lower().startswith('linux'):
        uri = 'file://' + sound_file
        global loop
        loop = glib.MainLoop()
        playSoundClass = playSound(uri, loop=loop)
        thread.start_new_thread(playSoundClass.start, ())
        gobject.threads_init()
        loop.run()
    elif sys.platform.lower().startswith('darwin'):
        os.system("afplay " + sound_file)

def timestamp():
    return strftime("%a, %d %b %Y %H:%M:%S", gmtime())

def timestamp_log():
    return strftime("%Y-%m-%d %H:%M:%S", gmtime())

def query(instance, severities, event_states, production_states, device_class):
    ZenBeep.info("\t%s: Querying %s" % (timestamp_log(), instance['short_name']))
    
    target_instance = instance['target_instance']
    zapi = ZAPI(debug = False, targetInstance = target_instance, zenossUser = username, zenossPassword = password)
    query_result = zapi.get_events(severity = severities, eventState = event_states, prodState = production_states, deviceClass = device_class)
    event_count = int(query_result['totalCount'])
    
    return event_count

def main():
    starting_column = 0
    # Setup some extra attributes that we need
    for instance in instances:
        instance['starting_column'] = starting_column
        instance['alert_line'] = False
        starting_column += len(instance['short_name']) + 2

    while 1:
        ZenBeep.info("\t%s: #### Starting new query cycle" % timestamp_log())
        os.system('clear')

        for instance in instances:
            num_events = 0
            
            # Run the query
            try:
                num_events = query(instance, severities, event_states, production_states, device_classes)
            except (urllib2.URLError, socket.timeout), e:
                ZenBeep.critical("\t%s: Query problem with %s (%s)" % (timestamp_log(), instance['short_name'], e))
                num_events = -1

            # Now lety's update
            if num_events > 0:
                print "%s%s events need to be ACK in %s at %s%s" % (bcolors.FAIL, str(num_events), instance['short_name'], timestamp(), bcolors.ENDC)
                play_sound(sound_file)
                ZenBeep.info("\t%s: %s events in %s" % (timestamp_log(), str(num_events), instance['short_name']))
            elif num_events < 0:
                print "%sProblem with query against %s at %s%s" % (bcolors.WARNING, instance['short_name'], timestamp(), bcolors.ENDC)
            else:
                print "%sAll events in %s are ACK at %s%s" % (bcolors.OKGREEN, instance['short_name'], timestamp(), bcolors.ENDC)
            
        time.sleep(cycle_time)

try:
    if len(instances) == 0:
       print "No targets specified"
       ZenBeep.info("No targets specified")
       sys.exit(0)

    if __name__=='__main__':
        main()

except (KeyboardInterrupt, SystemExit):
    sys.exit(0)
