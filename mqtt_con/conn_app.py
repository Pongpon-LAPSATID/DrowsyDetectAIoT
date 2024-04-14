import os
import sys
import logging
from datetime import datetime
import json

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

# The callback for when the client receives a CONNACK response from the server.
def on_connect(client, userdata, flags, reason_code, properties):
    logging.info('Connected to MQTT Broker.')
    client.subscribe(MQTT_CARID_LOG_TOPIC + '#')
    client.subscribe(MQTT_HB_TOPIC + '#')
    client.subscribe(MQTT_CARID_ALARM_TOPIC)

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

    # Case #1: If evt_type == log (i.e. if {"eyes":"closed"})
    if evt_type == 'log':
        dev_doc = dev_reg.find_one({'dev_id': dev_id})
        # Do the following if the dev_id of the hardware (which sent this mqtt message) is already registered in our database
        if dev_doc is not None:
            msg_data = json.loads(msg.payload) # get the payload (i.e. body) of the mqtt message received
            # insert this data into device_event database (class)
            dev_evts.insert_one({
                'dev_id': dev_id,
                'car_driver_id': car_driver_id,
                'eye_status': msg_data['eyes'], # eye_status ({'eye': ???}) from ESP32's drowsiness detection module
                'alarm_status': msg_data['alarm'], # alarm_status ({'alarm': ???}) from ESP32's drowsiness detection module
                'dev_location': msg_data['gps_lonlat'], # GPS location (lon/lat) from GPS module
                'value': msg_data['value'],
                'timestamp': msg_data['timestamp'] # timestamp record at real-time from ESP32's drowsiness detection module
            })

# start instance
mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
mqtt_client.enable_logger()
mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message
mqtt_client.connect(mqtt_broker, int(mqtt_port), 60)
mqtt_client.loop_forever()