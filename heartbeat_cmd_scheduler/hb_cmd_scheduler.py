import os
import sys
import logging
from pymongo import MongoClient

import schedule
import time

import json
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

# MQTT topics
MQTT_CMD_TOPIC = os.getenv('MQTT_CMD_TOPIC', None)
if MQTT_CMD_TOPIC is None:
    logging.error('MQTT_CMD_TOPIC undefined.')
    sys.exit(1)

# start mqtt instance
mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
mqtt_client.enable_logger()
mqtt_client.connect(mqtt_broker, int(mqtt_port), 60)

def publish_msg(client, topic, payload_dict):
    payload = json.dumps(payload_dict)
    client.publish(topic, payload)


def hb_check_cmd_send():
    # call the databases
    dev_db = mongo_client.dev_db
    dev_log = dev_db.device_log
    dev_logs = list(dev_log.find({}, {'dev_id': True}))
    dev_id_list = [device['dev_id'] for device in dev_logs]
    #dev_latestms_dict = dict.fromkeys(dev_id_list, 0) # initialize all latest_hb at 0 for each dev_id

    # if no heartbeat after 5 sec from the latest heartbeat, status --> offline
    for devid in dev_id_list:
        #latest_hb = dev_latestms_dict[devid]
        latest_hb = dev_log.find_one({'dev_id': devid}, {'_id': False})['latest_hb']
        current_ms = time.time()
        print(f'current_ms: {current_ms}')
        if ((current_ms - latest_hb) >= 5):
            dev_log.update_one({'dev_id': devid}, {'$set':{'status':'offline'}})
            print(f'dev_id: {devid} || status: "offline" || latest_hb = {latest_hb}')
        else:
            dev_log.update_one({'dev_id': devid}, {'$set':{'status':'online'}})
            print(f'dev_id: {devid} || status: "online" || latest_hb = {latest_hb}')

        # publish the current cmd (activation command) for each dev_id from the database
        cmd = dev_log.find_one({'dev_id': devid}, {'_id': 0, 'CMD': 1})['CMD']
        cmd_payload = {"CMD":cmd}
        print(f'{MQTT_CMD_TOPIC}{devid}')
        publish_msg(mqtt_client, f'{MQTT_CMD_TOPIC}{devid}', cmd_payload)
        print(f"{devid} || CMD: {cmd} published")


schedule.every(5).seconds.do(hb_check_cmd_send)

while True:
    schedule.run_pending()
    time.sleep(1)