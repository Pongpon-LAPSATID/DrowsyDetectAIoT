import os
import sys
import logging
from datetime import datetime
import json

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder

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

@app.get('/api/devreg/{dev_id}')
async def on_devreg(dev_id: str, request: Request):
    resp = {'status': 'OK'}
    #
    dev_db = mongo_client.dev_db
    dev_reg = dev_db.device
    new_dev = {
        'dev_id': dev_id,
        'car_driver_id': None,
        'created_at': None,
        'registered_at': datetime.now()
    }
    dev_id = dev_reg.insert_one(new_dev).inserted_id
    resp['dev_id'] = str(dev_id)
    return jsonable_encoder(resp)

@app.get('/api/devlog/{dev_id}')
async def on_devlist(request: Request):
    resp = {'status': 'OK'}
    dev_db = mongo_client.dev_db
    dev_reg= dev_db.device
    resp['devices'] = list(dev_reg.find({}, {'_id': False}))
    return jsonable_encoder(resp)

@app.get('/api/devevts/{dev_id}')
async def on_devevts(dev_id: str, request: Request):
    resp = {'status': 'OK'}
    dev_db = mongo_client.dev_db
    dev_evts = dev_db.dev_events
    resp['dev_id'] = dev_id
    #resp['car_driver_id'] = None # No need here. It is already in the document collection
    resp['dev_evts'] = list(dev_evts.find({'dev_id': dev_id}, {'_id': False}))
    return jsonable_encoder(resp)