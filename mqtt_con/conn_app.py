import os
import sys
import logging
from datetime import datetime, timedelta
from pytz import timezone
import json
import time

from pymongo import MongoClient

import paho.mqtt.client as mqtt

from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    PushMessageRequest,
    TextMessage
)
from pprint import pprint

# timezone config
tz = timezone(os.getenv('TZ', None))
if tz is None:
    logging.error('TZ undefined.')
    sys.exit(1)
timestamp = datetime.now(tz=tz)

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
MQTT_STATUS_TOPIC = os.getenv('MQTT_STATUS_TOPIC', None)
if MQTT_STATUS_TOPIC is None:
    logging.error('MQTT_STATUS_TOPIC undefined.')
    sys.exit(1)

# LINE Bot Config
channel_access_token = os.getenv('LINE_ACCESS_TOKEN', None)
if channel_access_token is None:
    print('Failed to retrieve LINE_ACCESS_TOKEN from environment variables.')
    sys.exit(1)
# user_id of the LINE Account that LINE Bot will send alert message to
## use for demo only
## for real production; use LINE Messaging API to collect all userId securely without explicitly writing them out manually in .env
user_1_id = os.getenv('USER_1_ID', None)
if user_1_id is None:
    print('Failed to retrieve USER_1_ID from environment variables.')
    sys.exit(1)

configuration = Configuration(
    access_token=channel_access_token
)


# The callback for when the client receives a CONNACK response from the server.
def on_connect(client, userdata, flags, reason_code, properties):
    logging.info('Connected to MQTT Broker.')
    client.subscribe(MQTT_HB_TOPIC + '#')
    client.subscribe(MQTT_CARID_LOG_TOPIC + '#')
    client.subscribe(MQTT_CARID_ALARM_TOPIC + '#')
    client.subscribe(MQTT_STATUS_TOPIC + '#')
    client.subscribe(MQTT_CMD_TOPIC + '#')
    

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
    #car_owner_db = car_db.car_owner # (car owner = admin level user): admin_id, auth

    # extract dev_id from its corresponding mqtt topic: either MQTT_CARID_LOG or MQTT_CARID_ALARM Topic
    dev_id = msg.topic.split('/')[-1]
    print(f'dev_id: {dev_id}')
    # retrieve car_driver_id from dev_id
    
    # extract the mqtt payload received
    msg_data = json.loads(msg.payload, strict=False)

    # get the event type: log, alarm, or heartbeat
    evt_type = msg.topic.split('/')[-2]
    print(f'evt_type: {evt_type}')
    
    
    # for CMD mqtt topic
    if (evt_type == 'command'):
        print(f'MQTT Topic: command || Payload: {msg_data}')
    
    # subscribe status from hardware module + heartbeat detector backend module
    if evt_type == 'status':
        dev_doc = dev_reg.find_one({'dev_id': dev_id}, {'_id': False})
        if dev_doc is not None:
            dev_log.update_one({'dev_id': dev_id}, {'$set':{'status': msg_data['status']}})
    
    # for heartbeat mqtt topic
    if evt_type == 'heartbeat':
        dev_doc = dev_reg.find_one({'dev_id': dev_id}, {'_id': False})
        if dev_doc is not None: # recognize only registered dev_id's heartbeat
            #dev_latestms_dict[dev_id] = msg_data['timestamp']
            dev_log.update_one({'dev_id': dev_id}, {'$set':{'latest_hb': msg_data['timestamp']}})

    # for dev_evts mqtt topics
    #if (evt_type == 'log') or (evt_type == 'alarm'): # subject to change later, depending on hardware implementation result
    if (evt_type == 'log'):
        car_driver_id = dev_reg.find_one({'dev_id':dev_id}, {'_id': False})['car_driver_id']
        print(f'dev_id: {dev_id} || car_driver_id: {car_driver_id}')
        # check the dev_id, car_driver_id correctness
        ## proceed only if they are valid
        if (msg_data['dev_id'] == dev_id) and (msg_data['car_driver_id'] == car_driver_id):
            dev_doc = dev_reg.find_one({'dev_id': dev_id}, {'_id':False})
            # Do the following if the dev_id of the hardware (which sent this mqtt message) is already registered in our database
            if dev_doc is not None:
                #msg_data = json.loads(msg.payload) # get the payload of the mqtt mesage received
                # insert msg_data into device_event database
                dev_evts.insert_one({
                    'dev_id': msg_data['dev_id'],
                    'car_driver_id': msg_data['car_driver_id'],
                    'eye_status': msg_data['eye_status'], # eye_status ({'eye': ???}) from ESP32's drowsiness detection module
                    'alarm_status': msg_data['alarm_status'], # alarm_status ({'alarm': ???}) from ESP32's drowsiness detection module
                    #'dev_location': msg_data['gps_lonlat'], # GPS location (lon/lat) from GPS module
                    #'value': msg_data['value'], # may be omitted; Prof's example uses 'value' as 'status': 'silent', 'detected', etc.
                    'timestamp': msg_data['timestamp'] # timestamp record at real-time from ESP32's drowsiness detection module
                })
                
                # send LINE Bot Alert if {'alarm':1} for 1 min continuously
                #if evt_type == 'alarm':
                if msg_data['alarm_status'] == "1":
                    #dev_log.update_one({'dev_id': dev_id}, {'$set':{'status':'alarm'}})
                    dev_evts_last60 = list(dev_evts.find({'dev_id':dev_id}, {'_id': False}))[-10:]
                    dev_evts_last60 = dev_evts_last60[-1::-1]
                    dev_evts_lastmin = []
                    prev_iter_timestamp = dev_log.find_one({'dev_id':dev_id}, {'prev_iter_timestamp':True})['prev_iter_timestamp']
                    #slp_counter = dev_log.find_one({'dev_id':dev_id}, {'slp_counter':True})['slp_counter']
                    alert_delay_counter = dev_log.find_one({'dev_id':dev_id}, {'alert_delay_counter':True})['alert_delay_counter']
                    print('==============')
                    print(f'dev_id: {dev_id} is alarming !!')
                    print(f'prev_iter_timestamp: {prev_iter_timestamp}')

                    for i in dev_evts_last60:
                        # count sleep counter only if alarm = 1 (ON) and that timestamp is not far apart from its previous timestamp more than 5 sec
                        #if (i['alarm_status'] == "1") and ((int(prev_iter_timestamp) - int(i['timestamp'])) <= 5):
                        current_timestamp = datetime.strptime(i['timestamp'], "%Y-%m-%d %H:%M:%S.%f")
                        if prev_iter_timestamp == 0:
                            prev_iter_timestamp = current_timestamp + timedelta(seconds=1)
                        #if (i['alarm_status'] == "1") and (((prev_iter_timestamp - current_timestamp) <= timedelta(seconds=5)) or (prev_iter_timestamp == 0)): # for actual use
                        if (i['alarm_status'] == "1") and ((prev_iter_timestamp - current_timestamp) <= timedelta(seconds=5)):
                            dev_evts_lastmin.append(i)
                            # update prev_iter_timestamp variable
                            #prev_iter_timestamp = int(i['timestamp']) # for mock test
                            prev_iter_timestamp = current_timestamp # for actual use

                            # update prev_iter_timestamp data in the dev_log database
                            dev_log.update_one({'dev_id': dev_id}, {'$set':{'prev_iter_timestamp':prev_iter_timestamp}})

                            
                        else:
                            break
                    
                    print(f'latest_timestamp: {msg_data["timestamp"]}')
                    print('------')
                    slp_counter = max(1, len(dev_evts_lastmin))
                    dev_log.update_one({'dev_id':dev_id}, {'$set':{'slp_counter':slp_counter}})
                    print(f'slp_counter: {slp_counter}')

                    if (slp_counter == 10):
                        if (alert_delay_counter % 10 == 0):
                            driver_name = car_driver_db.find_one({'car_driver_id':car_driver_id}, {'_id':False})['driver_name']
                            driver_address = car_driver_db.find_one({'car_driver_id':car_driver_id}, {'_id':False})['driver_address']
                            driver_contact = car_driver_db.find_one({'car_driver_id':car_driver_id}, {'_id':False})['driver_contact']
                            driver_registered_at = car_driver_db.find_one({'car_driver_id':car_driver_id}, {'_id':False})['driver_registered_at']
                            car_model = car_driver_db.find_one({'car_driver_id':car_driver_id}, {'_id':False})['car_model']
                            car_created_at = car_driver_db.find_one({'car_driver_id':car_driver_id}, {'_id':False})['car_created_at']
                            
                            # LINE Bot Alert push message
                            ## for mock test
                            #print(f'dev_id: {dev_id} alarms continuously for greater than 1 min !\nContact Car Driver Immediately !!\nContact:\ncar_driver_id: {car_driver_id}\ndriver_name: {driver_name}\ndriver_address: {driver_address}\ndriver_contact: {driver_contact}\ndriver_registered_at: {driver_registered_at}\ncar_model: {car_model}\ncar_created_at: {car_created_at}')
                        
                            ## for actual implementation
                            with ApiClient(configuration) as api_client:
                                line_bot_api = MessagingApi(api_client) # api_instance
                                driver_name = car_driver_db.find_one({'car_driver_id':car_driver_id}, {'_id':False})['driver_name']
                                driver_address = car_driver_db.find_one({'car_driver_id':car_driver_id}, {'_id':False})['driver_address']
                                driver_contact = car_driver_db.find_one({'car_driver_id':car_driver_id}, {'_id':False})['driver_contact']
                                driver_registered_at = car_driver_db.find_one({'car_driver_id':car_driver_id}, {'_id':False})['driver_registered_at']
                                car_model = car_driver_db.find_one({'car_driver_id':car_driver_id}, {'_id':False})['car_model']
                                car_created_at = car_driver_db.find_one({'car_driver_id':car_driver_id}, {'_id':False})['car_created_at']
                                noti_text = TextMessage(text=f'dev_id: {dev_id} alarms continuously for greater than 1 min !\nContact Car Driver Immediately !!\nContact:\ncar_driver_id: {car_driver_id}\ndriver_name: {driver_name}\ndriver_address: {driver_address}\ndriver_contact: {driver_contact}\ndriver_registered_at: {driver_registered_at}\ncar_model: {car_model}\ncar_created_at: {car_created_at}')
                                #x_line_retry_key = 'x_line_retry_key_example' # make it yourself

                                push_message_request = PushMessageRequest(
                                    to=user_1_id,
                                    messages=[noti_text]
                                )
                                try:
                                    api_response = line_bot_api.push_message(push_message_request)
                                    print("The response of MessagingApi->push_message:\n")
                                    pprint(api_response)

                                except Exception as e:
                                    print("Exception when calling MessagingApi->push_message: %s\n" % e)
                            
                        alert_delay_counter += 1
                        dev_log.update_one({'dev_id':dev_id}, {'$set':{'alert_delay_counter':alert_delay_counter}})

                    else:
                        alert_delay_counter = 0
                        dev_log.update_one({'dev_id':dev_id}, {'$set':{'alert_delay_counter':alert_delay_counter}})

                    print(f'alert_delay_counter: {alert_delay_counter}')
                    # reset prev_iter_timestamp to 0 to prepare for next mqtt message    
                    prev_iter_timestamp = 0
                    dev_log.update_one({'dev_id': dev_id}, {'$set':{'prev_iter_timestamp':prev_iter_timestamp}})
                    print('==============')

                #elif msg_data['alarm_status'] == "0":
                #    dev_log.update_one({'dev_id': dev_id}, {'$set':{'status':'activated'}})

# start instance
mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
mqtt_client.enable_logger()
mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message
mqtt_client.connect(mqtt_broker, int(mqtt_port), 60)
mqtt_client.loop_forever()