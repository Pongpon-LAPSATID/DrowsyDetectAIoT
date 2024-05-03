import os
import sys
import logging
from datetime import datetime
from pytz import timezone
import json

from fastapi import FastAPI, Request, HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

import paho.mqtt.client as mqtt

from pymongo import MongoClient

import pandas as pd

# timezone config
tz = timezone(os.getenv('TZ', None))
if tz is None:
    logging.error('TZ undefined.')
    sys.exit(1)


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
    timestamp = datetime.now(tz=tz)
    data['timestamp'] = timestamp
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
    #if dev_doc is not None:
    dev_evts.insert_one(data)
        
    #else:
    #    resp['error_message'] = f'400: Only registered dev_id is acceptable.'
    #    raise HTTPException(status_code=400, detail="Only registered dev_id is acceptable")

@app.get('/api/dbexport/{db}')
async def dbexport(db: str, request: Request):
    resp = {'status':'OK'}
    # call the database
    dev_db = mongo_client.dev_db
    car_db = mongo_client.car_db
    if db == 'device':
        target_db = dev_db.device
    elif db == 'device_log':
        target_db = dev_db.device_log
    elif db == 'device_events':
        target_db = dev_db.device_events
    elif db == 'car_driver':
        target_db = car_db.car_driver
    elif db == 'car_owner':
        target_db = car_db.car_owner
    print(f'target_db = {target_db}')

    db_data = list(target_db.find({}, {'_id':False}))
    resp['db_data'] = db_data
    
    # export csv
    db_data_df = pd.DataFrame(db_data)
    db_data_df.to_csv(os.path.join(
        os.path.dirname(os.path.abspath(__file__)), 
        f"{timestamp.strftime('%Y%m%d%H%M%S')}_{db}.csv"), 
        index=False)
    
    return jsonable_encoder(resp)
