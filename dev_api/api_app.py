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

# start instance
app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

@app.get('/api/devreg/{dev_id}')
async def on_devreg(dev_id: str, request: Request):
    resp = {'status': 'OK'}
    #
    dev_db = mongo_client.dev_db
    # register new dev_id
    dev_reg = dev_db.device
    new_dev = {
        'dev_id': dev_id,
        'car_driver_id': None,
        'created_at': None,
        'registered_at': datetime.now()
    }
    dev_id = dev_reg.insert_one(new_dev).inserted_id
    resp['dev_id'] = str(dev_id)
    # register new dev_log for the new dev_id
    dev_log = dev_db.device_log
    new_devlog = {
        'dev_id': dev_id,
        'status': 'offline'
    }
    dev_id_log = dev_log.insert_one(new_devlog).inserted_id
    resp['log'] = str(dev_id_log)
    return jsonable_encoder(resp)

@app.get('/devregister')
async def on_devregister(request: Request):
    return templates.TemplateResponse(
        request=request, name="devregister.html", content={"dummy":0}
    )

@app.post('/api/devregister')
async def on_devregister(request: Request):
    resp = {'status': 'OK'}
    #
    dev_db = mongo_client.dev_db
    # register new dev_id
    dev_reg = dev_db.device
    data = await request.json()
    dev_doc = dev_reg.find_one({'dev_id': data['dev_id']}, {'_id': False})
    if dev_doc is not None:
        resp['error_message'] = f'409: duplicated dev_id is not acceptable'
        raise HTTPException(status_code=409, detail="Duplicated dev_id is not acceptable")
        #return jsonable_encoder(resp)

    # check for abnormal case 2: missing info
    for key in data.keys():
        value = data[key]
        if value == "":
            resp['error_message'] = f'400: missing required info; {data[key]} is required'
            raise HTTPException(status_code=400, detail=f'missing required info; {data[key]} is required')
            #return jsonable_encoder(resp)
    data['registered_at'] = datetime.now()
    dev_id = dev_reg.insert_one(data).inserted_id
    resp['registrar'] = str(dev_id)
    return jsonable_encoder(resp)


@app.get('/devregedit')
async def on_devregedit(request: Request):
    return templates.TemplateResponse(
        request=request, name="devregedit.html", content={"dummy":0}
    )

@app.post('/api/devregedit')
async def on_devregister(request: Request):
    resp = {'status': 'OK'}
    #
    dev_db = mongo_client.dev_db
    # register new dev_id
    dev_reg = dev_db.device
    data = await request.json()
    dev_doc = dev_reg.find_one({'dev_id': data['dev_id']}, {'_id': False})
    if dev_doc is not None:
        dev_reg.update_one({'dev_id': data['dev_id']}, {'$set':{'car_driver_id':data['car_driver_id']}})
        dev_reg.update_one({'dev_id': data['dev_id']}, {'$set':{'created_at':data['created_at']}})
        dev_reg.update_one({'dev_id': data['dev_id']}, {'$set':{'registered_at':datetime.now()}})
    
    resp['dev_id editted'] = str(dev_reg.find_one({'dev_id': data['dev_id']}, {'_id': False}))
    return jsonable_encoder(resp)

@app.get('/api/alldevlist')
async def on_devlist(request: Request):
    resp = {'status':'OK'}
    dev_db = mongo_client.dev_db
    dev_reg = dev_db.device
    resp['devices'] = list(dev_reg.find({}, {'_id':False}))
    return jsonable_encoder(resp)

@app.get('/api/alldevevts')
async def on_devevts(request: Request):
    resp = {'status':'OK'}
    dev_db = mongo_client.dev_db
    dev_evts = dev_db.device_events
    resp['dev_evts'] = list(dev_evts.find({}, {'_id':False}))
    return jsonable_encoder(resp)

@app.get('/api/devlist/{dev_id}')
async def on_devlist(dev_id: str, request: Request):
    resp = {'status': 'OK'}
    dev_db = mongo_client.dev_db
    dev_reg= dev_db.device
    resp['devices'] = list(dev_reg.find({'dev_id': dev_id}, {'_id': False}))
    return jsonable_encoder(resp)

@app.get('/api/devevts/{dev_id}')
async def on_devevts(dev_id: str, request: Request):
    resp = {'status': 'OK'}
    dev_db = mongo_client.dev_db
    dev_evts = dev_db.device_events
    resp['dev_id'] = dev_id
    #resp['car_driver_id'] = None # No need here. It is already in the document collection
    resp['dev_evts'] = list(dev_evts.find({'dev_id': dev_id}, {'_id': False}))
    return jsonable_encoder(resp)

@app.get('api/devlog')
async def on_devlog(request: Request):
    ''' See the current status of each registered device '''
    resp = {'status':'OK'}
    dev_db = mongo_client.dev_db
    dev_log = dev_db.device_log
    data = await request.json()
    resp['log'] = list(dev_log.find({}, {'_id': False}))
    return jsonable_encoder(resp)