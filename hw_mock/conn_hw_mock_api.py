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

from pymongo import MongoClient

# logging configuration
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# for hw_mock_api: Exclude them from the real conn_app.py script
app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

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
    ## input hardware mock data if dev_id inputted is already registered
    dev_db = mongo_client.dev_db
    dev_reg = dev_db.device
    dev_evts = dev_db.device_events
    dev_doc = dev_reg.find_one({'dev_id': data['dev_id']}, {'_id': False})
    # input only data from registered device
    if dev_doc is not None:
        dev_evts.insert_one(data)
        resp['data_inputted'] = str(data)
        return jsonable_encoder(resp)
    else:
        resp['error_message'] = f'400: Only registered dev_id is acceptable.'
        raise HTTPException(status_code=400, detail="Only registered dev_id is acceptable")