import os
import sys
import logging
from datetime import datetime
import json
import time

from pymongo import MongoClient

import paho.mqtt.client as mqtt

# logging configuration
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# pymongo configuration
mongo_host = os.getenv('MONGO_HOST', None)
if mongo_host is None:
    logging.error('MONGO_HOST undefined.')
    sys.exit(1)
mongo_port = os.getenv('MONGO_PORT', None)
if mongo_port is None:
    logging.error('MONGO_PORT undefined.')
    sys.exit(1)
mongo_client = MongoClient(mongo_host, int(mongo_port))

# mqtt configuration
mqtt_broker = os.getenv('MQTT_BROKER', None)
if mqtt_broker is None:
    logging.error('MQTT_BROKER undefined.')
    sys.exit(1)
mqtt_port = os.getenv('MQTT_PORT', None)
if mqtt_port is None:
    logging.error('MQTT_PORT undefined.')
    sys.exit(1)

# MQTT data sources
MQTT_CARID_LOG_TOPIC = os.getenv('MQTT_CARID_LOG_TOPIC', None)
if MQTT_CARID_LOG_TOPIC is None:
    logging.error('MQTT_CARID_LOG_TOPIC undefined.')
    sys.exit(1)
MQTT_HB_TOPIC = os.getenv('MQTT_HB_TOPIC', None)
if MQTT_HB_TOPIC is None:
    logging.error('MQTT_HB_TOPIC undefined.')
    sys.exit(1)
MQTT_CARID_ALARM_TOPIC = os.getenv('MQTT_CARID_ALARM_TOPIC', None)
if MQTT_CARID_ALARM_TOPIC is None:
    logging.error('MQTT_CARID_ALARM_TOPIC undefined.')
    sys.exit(1)
MQTT_CMD_TOPIC = os.getenv('MQTT_CMD_TOPIC', None)
if MQTT_CMD_TOPIC is None:
    logging.error('MQTT_CMD_TOPIC undefined.')
    sys.exit(1)

# The callback for when the client receives a CONNACK response from the server.
def on_connect(client, userdata, flags, reason_code, properties):
    logging.info('Connected to MQTT Broker.')
    client.subscribe(MQTT_HB_TOPIC + '#')
    client.subscribe(MQTT_CARID_LOG_TOPIC + '#')
    client.subscribe(MQTT_CARID_ALARM_TOPIC + '#')

def on_message(client, userdata, msg):
    logging.info('Received message: %s from %s', msg.payload, msg.topic)
    # database & its collections for data from ESP32 data
    dev_db = mongo_client.dev_db
    dev_reg = dev_db.device # dev_id, car_driver_id, created_at, registered_at
    dev_log = dev_db.device_log # device_log_id: auto INC, dev_id, status
    dev_evts = dev_db.device_events # device_event_id: auto INC, dev_id, car_driver_id, eye_status, alarm_status, dev_location, value, timestamp
    # database & its collections for 
    car_db = mongo_client.car_db
    car_driver_db = car_db.car_driver # car_driver_db: auto INC, car_model, car_created_at, driver_name, driver_address, driver_contact, driver_registered_at
    car_owner_db = car_db.car_owner # (car owner = admin level user): admin_id, auth

    # extract dev_id from its corresponding mqtt topic: either MQTT_CARID_LOG or MQTT_CARID_ALARM Topic
    dev_id = msg.topic.split('/')[-1]

    # retrieve car_driver_id from dev_id
    car_driver_id = dev_reg.find_one({'dev_id':dev_id}, {'_id': False})['car_driver_id']

    # get the event type: log, alarm, or heartbeat
    evt_type = msg.topic.split('/')[-2]

    # for heartbeat mqtt topic
    if evt_type == 'heartbeat':
        dev_doc = dev_reg.find_one({'dev_id': dev_id}, {'_id': False})
        if dev_doc is not None:
            msg_data = json.loads(msg.payload)
            latest_ms = round(msg_data['timestamp'] * 1000)

            if (round(time.time()*1000) - latest_ms) >= 3000:
                dev_log.update_one({'dev_id': dev_id}, {'$set':{'status':'offline'}})
            else:
                dev_log.update_one({'dev_id': dev_id}, {'$set':{'status':'online'}})

    # publish mqtt cmd topic; send {'CMD': ON} to ESP32 board
    ## send cmd topic to hardware to activate the drowsy_detect system
    cmd_dict = {'CMD': 'ON'} # {'CMD': 'ON'}
    if mqtt_client.connected():
        try:
            cmd_json = json.dumps(cmd_dict)
            mqtt_client.publish(MQTT_CMD_TOPIC, cmd_json)
        except Exception as e:
            print(f'Error; Exception: {e}')
            cmd_dict['CMD'] = 'OFF'
            print(f'CMD = OFF')
    else:
        pass

    # for dev_evts mqtt topics
    if (evt_type == 'log') or (evt_type == 'alarm'): # subject to change later, depending on hardware implementation result
        dev_doc = dev_reg.find_one({'dev_id': dev_id}, {'_id':False})
        # Do the following if the dev_id of the hardware (which sent this mqtt message) is already registered in our database
        if dev_doc is not None:
            msg_data = json.loads(msg.payload) # get the payload of the mqtt mesage received
            # insert msg_data into device_event database
            dev_evts.insert_one({
                'dev_id': dev_id,
                'car_driver_id': car_driver_id,
                'eye_status': msg_data['eyes'], # eye_status ({'eye': ???}) from ESP32's drowsiness detection module
                'alarm_status': msg_data['alarm'], # alarm_status ({'alarm': ???}) from ESP32's drowsiness detection module
                'dev_location': msg_data['gps_lonlat'], # GPS location (lon/lat) from GPS module
                'value': msg_data['value'], # may be omitted; Prof's example uses 'value' as 'status': 'silent', 'detected', etc.
                'timestamp': msg_data['timestamp'] # timestamp record at real-time from ESP32's drowsiness detection module
            })

    ''' # For case that conn_app.py has to command the buzzer to alarm
    # check the status of that device
    dev_status_log = dev_log.find_one({'dev_id': dev_id}, {'_id': False})

    # check alarm status of that device
    if dev_status_log['status'] == 'alarm':
        dev_alarm = 1 # alarm == ON
    else:
        dev_alarm = 0 # alarm == OFF

    # Case #1: If evt_type == log (i.e. if {"eyes":"closed"})
    if evt_type == 'log':
        dev_doc = dev_reg.find_one({'dev_id': dev_id})
        # Do the following if the dev_id of the hardware (which sent this mqtt message) is already registered in our database
        if dev_doc is not None:
            # if status of that device is 'activated' or 'alarm'
            if (dev_status_log['status'] == 'activated') or (dev_status_log['status'] == 'alarm'):
                msg_data = json.loads(msg.payload) # get the payload (i.e. body) of the mqtt message received
                # insert this data into device_event database (class)
                dev_evts.insert_one({
                    'dev_id': dev_id,
                    'car_driver_id': car_driver_id,
                    'eye_status': msg_data['eyes'], # eye_status ({'eye': ???}) from ESP32's drowsiness detection module
                    'alarm_status': dev_alarm, # or use msg_data['alarm'] # alarm_status ({'alarm': ???}) from ESP32's drowsiness detection module
                    'dev_location': msg_data['gps_lonlat'], # GPS location (lon/lat) from GPS module
                    'value': msg_data['value'], # may be omitted; Prof's example uses 'value' as 'status': 'silent', 'detected', etc.
                    'timestamp': msg_data['timestamp'] # timestamp record at real-time from ESP32's drowsiness detection module
                })

    # Case #2: If evt_type == alarm
    elif evt_type == 'alarm':
        # check whether this dev_id is already registered
        dev_doc = dev_reg.find_one({'dev_id': dev_id})
        if dev_doc is not None:
            # get the data of the message
            msg_data = json.loads(msg.payload)
            # check the 'eye_status' of the last 3 doc of this dev_id
            dev_evts_3 = dev_evts.find({'dev_id': dev_id}, {'_id': False}, {'eye_status': True})['dev_evts'][-3:]
            sleep_counter = 0
            for evt in dev_evts_3:
                if evt['eye_status'] == 1:
                    sleep_counter += 1
            if sleep_counter == 3:
                sleep = True # car driver's eyes have been closed for 3 seconds (--> {'alarm':1})
                dev_log.update_one({'dev_id': dev_id}, {'$set':{'status':'alarm'}})
            else:
                sleep = False

            ## 2.1 (If {'eyes':0} for 3 consecutive timestamps) OR (If {'alarm':1})
            if (sleep == True) or (dev_alarm == 1):
                # insert this data into device_event database
                dev_evts.insert_one({
                    'dev_id': dev_id,
                    'car_driver_id': car_driver_id,
                    'eye_status': msg_data['eyes'],

                })
    '''


    
# start instance
mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
mqtt_client.enable_logger()
mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message
mqtt_client.connect(mqtt_broker, int(mqtt_port), 60)
mqtt_client.loop_forever()