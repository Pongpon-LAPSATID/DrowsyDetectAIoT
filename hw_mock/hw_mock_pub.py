import os
import sys
import logging
import schedule
import time
from datetime import datetime
import paho.mqtt.client as mqtt
import json


from pymongo import MongoClient

# logging config
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


dev_id = "dev_01"
dev_db = mongo_client.dev_db
dev_log = dev_db.device_log


# mqtt configuration
mqtt_broker = os.getenv('MQTT_BROKER', None)
if mqtt_broker is None:
    logging.error('MQTT_BROKER undefined.')
    sys.exit(1)
mqtt_port = os.getenv('MQTT_PORT', None)
if mqtt_port is None:
    logging.error('MQTT_PORT undefined.')
    sys.exit(1)

# MQTT topics
MQTT_CMD_TOPIC = os.getenv('MQTT_CMD_TOPIC', None)
if MQTT_CMD_TOPIC is None:
    logging.error('MQTT_CMD_TOPIC undefined.')
    sys.exit(1)
MQTT_HB_TOPIC = os.getenv('MQTT_HB_TOPIC', None)
if MQTT_HB_TOPIC is None:
    logging.error('MQTT_HB_TOPIC undefined.')
    sys.exit(1)
MQTT_STATUS_TOPIC = os.getenv('MQTT_STATUS_TOPIC', None)
if MQTT_STATUS_TOPIC is None:
    logging.error('MQTT_STATUS_TOPIC undefined.')
    sys.exit(1)
MQTT_CARID_LOG_TOPIC = os.getenv('MQTT_CARID_LOG_TOPIC', None)
if MQTT_CARID_LOG_TOPIC is None:
    logging.error('MQTT_CARID_LOG_TOPIC undefined.')
    sys.exit(1)


def on_connect(client, userdata, flags, reason_code, properties):
    logging.info('Connected to MQTT Broker')
    client.subscribe(MQTT_CMD_TOPIC + '#')

def on_message(client, userdata, msg):
    logging.info('Received message: %s from %s', msg.payload, msg.topic)
    global cmd
    evt_type = msg.topic.split('/')[-2]

    if evt_type == 'command':
        cmd = json.loads(msg.payload())['CMD']

# start mqtt instance
mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
mqtt_client.enable_logger()
mqtt_client.connect(mqtt_broker, int(mqtt_port), 60)

def publish_msg(client, topic, payload_dict):
    payload = json.dumps(payload_dict)
    client.publish(topic, payload)
    logging.info('Published %s || %s', topic, payload)


def hw_mock(eye_status="1", alarm_status="1"):
    # eye_status, alarm_status can be only either "0" or "1"
    if eye_status != "1":
        alarm_status = "0"

    cmd = dev_log.find_one({"dev_id": dev_id}, {"_id": False})['CMD']

    hb_msg = {"heartbeat":"heartbeat","timestamp":time.time()}

    if cmd == True:
        detect_msg = {"dev_id": "dev_01", "car_driver_id": "cd_01", "eye_status": eye_status, "alarm_status": alarm_status, "timestamp": str(datetime.now())}
        if alarm_status == "1":
            status_msg = {"status":"alarm"}
        elif alarm_status == "0":
            status_msg = {"status":"activated"}

        logging.info('Current CMD: %s', cmd)
        publish_msg(mqtt_client, f'{MQTT_HB_TOPIC}{dev_id}', hb_msg)
        time.sleep(1)
        publish_msg(mqtt_client, f'{MQTT_STATUS_TOPIC}{dev_id}', status_msg)
        time.sleep(1)
        publish_msg(mqtt_client, f'{MQTT_CARID_LOG_TOPIC}{dev_id}', detect_msg)
        

    else:
        detect_msg = {"dev_id": "dev_01", "car_driver_id": "cd_01", "eye_status": "eye_status", "alarm_status": alarm_status, "timestamp": str(datetime.now())}
        status_msg = {"status":"online"}
        publish_msg(mqtt_client, f'{MQTT_HB_TOPIC}{dev_id}', hb_msg)
        time.sleep(1)
        publish_msg(mqtt_client, f'{MQTT_STATUS_TOPIC}{dev_id}', status_msg)
    
def hwmock():
    for i in range(5):
        print("eye_status: 0, alarm_status: 0")
        hw_mock(eye_status="0", alarm_status="0")


    for j in range(3):
        print("eye_status: 1, alarm_status: 0")
        hw_mock(eye_status="1", alarm_status="0")


    for k in range(120):
        print("eye_status: 1, alarm_status: 1")
        hw_mock(eye_status="1", alarm_status="1")


schedule.every(128).seconds.do(hwmock)

while True:
    schedule.run_pending()
    time.sleep(1)    







