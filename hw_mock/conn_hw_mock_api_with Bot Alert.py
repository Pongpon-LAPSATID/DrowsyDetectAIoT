import os
import sys
import logging
from datetime import datetime
import json

from fastapi import FastAPI, Request, HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

import paho.mqtt.client as mqtt

from pymongo import MongoClient

from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    PushMessageRequest,
    TextMessage
)

from pprint import pprint

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

# LINE Bot config
channel_access_token = os.getenv('LINE_ACCESS_TOKEN', None)
if channel_access_token is None:
    print('Failed to retrieve LINE_ACCESS_TOKEN from environment variables.')
    sys.exit(1)
user_1_id = os.getenv('USER_1_ID', None)
print(f'user_i_id: {user_1_id}')
if user_1_id is None:
    print('Failed to retrieve BOT_CHANNEL_ID from environment variables.')
    sys.exit(1)

configuration = Configuration(
    access_token=channel_access_token
)

# mqtt config
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

# mqtt: for hw_mock only, exclude them out from conn_app.py
# The callback for when the client receives a CONNACK response from the server.
def on_connect(client, userdata, flags, reason_code, properties):
    logging.info('Connected to MQTT Broker.')
    #client.subscribe(MQTT_HB_TOPIC + '#')
    #client.subscribe(MQTT_CARID_LOG_TOPIC + '#')
    #client.subscribe(MQTT_CARID_ALARM_TOPIC + '#')

'''
mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
mqtt_client.enable_logger()
mqtt_client.on_connect = on_connect
mqtt_client.connect(mqtt_broker, int(mqtt_port), 60)

if mqtt_client.is_connected == False:
    print('HW_MOCK cannot connect to MQTT.')
    sys.exit(1)
else:
    print('HW_MOCK can connect to MQTT !')
'''

# for hw_mock_api: Exclude them from the real conn_app.py script
app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# hardware mock api
@app.get('/hwmock')
async def hwmock_datagen(request: Request):
    return templates.TemplateResponse(
        request=request, name="hwmock.html", context={"dummy":0}
    )

@app.post('/api/hwmock')
async def hwmock_datagen(request: Request):
    resp = {'status':'OK'}
    # get data from POST request
    data = await request.json()
    # input to device_event database
    ## check for abnormal case 2: missing info
    for key in data.keys():
        value = data[key]
        if value == "":
            resp['error_message'] = f'400: missing required info; {data[key]} is required'
            raise HTTPException(status_code=400, detail=f'missing required info; {data[key]} is required')
            #return jsonable_encoder(resp)
            
    ## publish/input hardware mock data if dev_id inputted is already registered
    dev_db = mongo_client.dev_db
    dev_reg = dev_db.device
    dev_evts = dev_db.device_events
    dev_doc = dev_reg.find_one({'dev_id': data['dev_id']}, {'_id': False})
    car_db = mongo_client.car_db
    car_driver_db = car_db.car_driver

    # input only data from registered device
    if dev_doc is not None:
        dev_evts.insert_one(data)
        '''
        data_str = json.dumps(data).encode('utf-8')
        mqtt_client.publish(os.path.join(MQTT_CARID_ALARM_TOPIC, data['dev_id']), data_str)
        resp['data_inputted'] = str(data)
        return jsonable_encoder(resp)
        '''
    else:
        resp['error_message'] = f'400: Only registered dev_id is acceptable.'
        raise HTTPException(status_code=400, detail="Only registered dev_id is acceptable")
    
    #if evt_type == 'alarm':
    dev_evts_lastmin = list(dev_evts.find({'dev_id': data['dev_id']}, {'alarm_status': True}))[-60:]
    #print(f'type(dev_evts_lastmin): {type(dev_evts_lastmin)}')
    #print(f'type(dev_evts_lastmin[0]): {type(dev_evts_lastmin[0])}')
    #print(f"dev_evts_lastmin:\n{dev_evts_lastmin}")
    slp_counter = 0
    for i in dev_evts_lastmin:
        if i['alarm_status'] == "1":
            slp_counter += 1
    print(f'slp_counter: {slp_counter}')
    
    slp_counter = 60 # for shortcut: comment this out for actual code

    # condition to send LINE Bot Notification
    if slp_counter == 60: # abs(slp_counter - 60) <= 10:
        # send LINE BOT Notification
        dev_id = data['dev_id']
        car_driver_id = data['car_driver_id']
        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client) # api_instance
            car_driver_name = car_driver_db.find_one({'car_driver_id':car_driver_id}, {'_id':False})['driver_name']
            contact = car_driver_db.find_one({'car_driver_id': car_driver_id}, {'_id':False})
            noti_text = TextMessage(text=f'dev_id: {dev_id} alarms continuously for 1 min !\nContact {car_driver_name} Immediately !!\nContact:\n{contact}')
            #x_line_retry_key = 'x_line_retry_key_example' # make it yourself

            push_message_request = PushMessageRequest(
                to=user_1_id,
                messages=[noti_text]
            )
            try:
                #api_response = line_bot_api.push_message(push_message_request, x_line_retry_key=x_line_retry_key)
                api_response = line_bot_api.push_message(push_message_request)
                print("The response of MessagingApi->push_message:\n")
                pprint(api_response)
            except Exception as e:
                print("Exception when calling MessagingApi->push_message: %s\n" % e)