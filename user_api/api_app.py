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
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# start instance
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

@app.get('/cardriverregister')
async def register(request: Request):
    return templates.TemplateResponse(
        request=request, name="cardriverreg.html", context={"dummy": 0} #html can access "dummy"'s value via the key "dummy"
    )

@app.get('/carownerregister')
async def register(request: Request):
    return templates.TemplateResponse(
        request=request, name="carownerreg.html", context={"dummy":0}
    )

@app.post('/api/cardriverreg')
async def register(request: Request):
    resp = {'status':'OK'}
    # call the car_driver_db
    car_db = mongo_client.car_db
    car_driver_db = car_db.car_driver
    #extract data from JSON
    data = await request.json()
    # check for abnormal case 1: duplicated user_id with the existing one in db
    cardv_doc = car_driver_db.find_one({'driver_name': data['driver_name']}, {'_id': False})
    if cardv_doc is not None:
        resp['error_message'] = f'409: duplicated driver_name is not acceptable'
        raise HTTPException(status_code=409, detail="Duplicated driver_name is not acceptable")
        #return jsonable_encoder(resp)

    # check for abnormal case 2: missing info
    for key in data.keys():
        value = data[key]
        if value == "":
            resp['error_message'] = f'400: missing required info; {data[key]} is required'
            raise HTTPException(status_code=400, detail=f'missing required info; {data[key]} is required')
            #return jsonable_encoder(resp)

    data['driver_registered_at'] = datetime.now()
    car_driver_db.insert_one(data)
    return jsonable_encoder(resp)

@app.post('api/carownerreg')
async def register(request: Request):
    resp = {'status':'OK'}
    # call the car_owner_db
    car_db = mongo_client.car_db
    car_owner_db = car_db.car_owner
    # receive data from body as json
    data = await request.json()
    # check for abnormal case 1: duplicated admin_id with the existing one in db
    carow_doc = car_owner_db.find_one({'admin_id': data['admin_id']}, {'_id': False})
    if carow_doc is not None:
        resp['error_message'] = f'409: duplicated admin_id is not acceptable'
        raise HTTPException(status_code=409, detail="Duplicated admin_id is not acceptable")
        #return jsonable_encoder(resp)

    # check for abnormal case 2: missing info
    for key in data.keys():
        value = data[key]
        if value == "":
            resp['error_message'] = f'400: missing required info; {data[key]} is required'
            raise HTTPException(status_code=400, detail=f'missing required info; {data[key]} is required')
            #return jsonable_encoder(resp)
    data['admin_registered_at'] = datetime.now()
    car_owner_db.insert_one(data)
    return jsonable_encoder(resp)

@app.get('/api/cardriverlist')
async def on_list(request: Request):
    resp = {'status':'OK'}
    # query and return all registered car drivers
    car_db = mongo_client.car_db
    car_driver_db = car_db.users
    resp['car_drivers'] = list(car_driver_db.find({}, {'_id':False}))
    return jsonable_encoder(resp)

@app.get('/api/carownerlist')
async def register(request: Request):
    resp = {'status':'OK'}
    # query and return all registered car owners
    car_db = mongo_client.car_db
    car_owner_db = car_db.car_owner
    resp['car_owners'] = list(car_owner_db.find({}, {'_id':False}))
    return jsonable_encoder(resp)