import os
import sys
import logging
from datetime import datetime
import json

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder

from pymongo import MongoClient

# logging config
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# pymongo config
mongo_host = os.getenv('MONGO_HOST', None)
if mongo_host is None:
    logging.error('MONGO_HOST undefined.')
    sys.exit(1)
mongo_port = os.getenv('MONGO_PORT', None)
if mongo_port is None:
    logging.error('MONGO_PORT undefined.')
    sys.exit(1)
#client = MongoClient('mongodb://admin:password@mongodb:27017')
mongo_client = MongoClient(mongo_host, int(mongo_port))

# start instance
app = FastAPI()

@app.post('/api/mock_hw_mqtt')
async def gen_mockdata(request: Request):
    resp = {'status':'OK'}
    # post mockup body data to dev_evts database
