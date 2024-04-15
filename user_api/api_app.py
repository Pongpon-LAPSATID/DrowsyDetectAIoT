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

@app.get('/register')
async def register(request: Request):
    return templates.TemplateResponse(
        request=request, name="index.html", context={"dummy": 0} #show that context to html using dummy
    )

@app.post('/api/register')
async def register(request: Request):
    resp = {'status':'OK'}
    # 
    user_db = mongo_client.user_db
    user_col = user_db.users
    #extract data from JSON
    data = await request.json()
    data["timestamp"] = datetime.now()
    # check for abnormal case 1: duplicated user_id with the existing one in db
    user_doc = user_col.find_one({'driver_name': data['driver_name']}, {'_id': False})
    if user_doc is not None:
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
    user_col.insert_one(data)
    return jsonable_encoder(resp)

@app.get('/api/list')
async def on_list(request: Request):
    resp = {'status':'OK'}
    # query and return all registered users
    user_db = mongo_client.user_db
    user_col = user_db.users
    resp['car_drivers'] = list(user_col.find({}, {'_id':False}))
    return jsonable_encoder(resp)