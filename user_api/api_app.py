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

from pymongo import MongoClient

# timezone config
tz = timezone(os.getenv('TZ', None))
if tz is None:
    logging.error('TZ undefined.')
    sys.exit(1)


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

@app.get('/cardriverreg')
async def on_cardriverregister(request: Request):
    return templates.TemplateResponse(
        request=request, name="cardriverreg.html", context={"dummy": 0} #html can access "dummy"'s value via the key "dummy"
    )

@app.get('/carownerreg')
async def on_carownerregister(request: Request):
    return templates.TemplateResponse(
        request=request, name="carownerreg.html", context={"dummy":0}
    )

@app.post('/api/cardriverreg')
async def on_cardriverreg(request: Request):
    resp = {'status':'OK'}
    # call the car_driver_db
    timestamp = datetime.now(tz=tz)
    car_db = mongo_client.car_db
    car_driver_db = car_db.car_driver
    car_owner_db = car_db.car_owner
    #extract data from JSON
    data = await request.json()
    # check for abnormal case 1: duplicated user_id with the existing one in db
    cardv_doc = car_driver_db.find_one({'car_driver_id': data['car_driver_id']}, {'_id': False})
    if cardv_doc is not None:
        resp['error_message'] = f'409: duplicated car_driver_id is not acceptable'
        raise HTTPException(status_code=409, detail="Duplicated car_driver_id is not acceptable")
        #return jsonable_encoder(resp)

    # check for abnormal case 2: missing info
    for key in data.keys():
        value = data[key]
        if value == "":
            resp['error_message'] = f'400: missing required info; {data[key]} is required'
            raise HTTPException(status_code=400, detail=f'missing required info; {data[key]} is required')
            #return jsonable_encoder(resp)

    # check for abnormal case 3: invalid admin_id, auth
    admins = list(car_owner_db.find({}, {'admin_id': True}))
    admin_id_list = [admin['admin_id'] for admin in admins]

    # invalid admin_id, auth inputted are not allowed
    if data['admin_id'] in admin_id_list:
        auth = data['auth']
        valid_auth = car_owner_db.find_one({'admin_id': data['admin_id']}, {'_id': 0, 'auth': 1})['auth']
        
        if auth == str(valid_auth):
            print(f'admin: {data["admin_id"]} authorized new device register.')
            data['driver_registered_at'] = timestamp
            # store only dev_reg data
            keys = ['car_driver_id', 'driver_name', 'driver_address', 'driver_contact', 'driver_registered_at', 'car_model', 'car_created_at']
            new_cdreg = {k: v for k, v in data.items() if k in keys}
            # register new car driver to car_driver database
            cd_objid = car_driver_db.insert_one(new_cdreg).inserted_id
            resp['dev_id'] = str(cd_objid)

            return jsonable_encoder(resp)
        
        else:
            resp['error_message'] = "Invalid admin_id or auth"
            print("Invalid admin_id or auth")
            raise HTTPException(status_code=400, detail="Invalid admin_id or auth. Authorization Failed.")
    else:
        resp['error_message'] = "Invalid admin_id or auth"
        print("Invalid admin_id or auth")
        raise HTTPException(status_code=400, detail="Invalid admin_id or auth. Authorization Failed.")


@app.post('/api/carownerreg')
async def on_carownerreg(request: Request):
    resp = {'status':'OK'}
    # call the car_owner_db
    timestamp = datetime.now(tz=tz)
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
    data['admin_registered_at'] = timestamp
    car_owner_db.insert_one(data)
    return jsonable_encoder(resp)

@app.get('/cardriverregedit')
async def on_cardriverregedit(request: Request):
    return templates.TemplateResponse(
        request=request, name="cardriverreg_edit.html", context={"dummy":0}
    )

@app.post('/api/cardriverregedit')
async def on_cardriverregedit(request: Request):
    resp = {'status':'OK'}
    # call the car_driver_db
    timestamp = datetime.now(tz=tz)
    car_db = mongo_client.car_db
    car_driver_db = car_db.car_driver
    car_owner_db = car_db.car_owner
    #extract data from JSON
    data = await request.json()
    # check for abnormal case 1: duplicated user_id with the existing one in db
    cardv_doc = car_driver_db.find_one({'car_driver_id': data['car_driver_id']}, {'_id': False})
    if cardv_doc is None:
        resp['error_message'] = f"403: Failed to Edit Data; {data['car_driver_id']} is not registered."
        raise HTTPException(status_code=403, detail=f"403: Failed to Edit Data; {data['car_driver_id']} is not registered.")
        #return jsonable_encoder(resp)

    # check for abnormal case 2: missing info
    for key in data.keys():
        value = data[key]
        if value == "":
            resp['error_message'] = f'400: missing required info; {data[key]} is required'
            raise HTTPException(status_code=400, detail=f'missing required info; {data[key]} is required')
            #return jsonable_encoder(resp)

    # check for abnormal case 3: invalid admin_id, auth
    admins = list(car_owner_db.find({}, {'admin_id': True}))
    admin_id_list = [admin['admin_id'] for admin in admins]

    # invalid admin_id, auth inputted are not allowed
    if data['admin_id'] in admin_id_list:
        auth = data['auth']
        valid_auth = car_owner_db.find_one({'admin_id': data['admin_id']}, {'_id': 0, 'auth': 1})['auth']
        
        if auth == str(valid_auth):
            print(f'admin: {data["admin_id"]} authorized new device register.')
            data['registered_at'] = timestamp
            # update data
            car_driver_db.update_one({'car_driver_id': data['car_driver_id']}, {'$set':{'driver_name':data['driver_name']}})
            car_driver_db.update_one({'car_driver_id': data['car_driver_id']}, {'$set':{'driver_address':data['driver_address']}})
            car_driver_db.update_one({'car_driver_id': data['car_driver_id']}, {'$set':{'driver_contact':data['driver_contact']}})
            car_driver_db.update_one({'car_driver_id': data['car_driver_id']}, {'$set':{'driver_registered_at':timestamp}})
            car_driver_db.update_one({'car_driver_id': data['car_driver_id']}, {'$set':{'car_model':data['car_model']}})
            car_driver_db.update_one({'car_driver_id': data['car_driver_id']}, {'$set':{'car_created_at':data['car_created_at']}})

            resp['edited_driver'] = str(car_driver_db.find_one({'car_driver_id':data['car_driver_id']}, {'_id':False}))
            return jsonable_encoder(resp)
        
        else:
            resp['error_message'] = "Invalid admin_id or auth"
            print("Invalid admin_id or auth")
            raise HTTPException(status_code=400, detail="Invalid admin_id or auth. Authorization Failed.")
    else:
        resp['error_message'] = "Invalid admin_id or auth"
        print("Invalid admin_id or auth")
        raise HTTPException(status_code=400, detail="Invalid admin_id or auth. Authorization Failed.")


@app.get('/carownerregedit')
async def on_carownerregedit(request: Request):
    return templates.TemplateResponse(
        request=request, name="carownerreg_edit.html", context={"dummy":0}
    )

@app.post('/api/carownerregedit')
async def on_carownerregedit(request: Request):
    resp = {'status':'OK'}
    # call the car_driver_db
    timestamp = datetime.now(tz=tz)
    car_db = mongo_client.car_db
    car_owner_db = car_db.car_owner
    #extract data from JSON
    data = await request.json()
    # check for abnormal case 1: duplicated user_id with the existing one in db
    carow_doc = car_owner_db.find_one({'admin_id': data['admin_id']}, {'_id': False})
    if carow_doc is None:
        resp['error_message'] = f"403: Failed to Edit Data; {data['admin_id']} is not registered."
        raise HTTPException(status_code=403, detail=f"403: Failed to Edit Data; {data['admin_id']} is not registered.")
        #return jsonable_encoder(resp)

    # check for abnormal case 2: missing info
    for key in data.keys():
        value = data[key]
        if value == "":
            resp['error_message'] = f'400: missing required info; {data[key]} is required'
            raise HTTPException(status_code=400, detail=f'missing required info; {data[key]} is required')
            #return jsonable_encoder(resp)
    car_owner_db.update_one({'admin_id': data['admin_id']}, {'$set':{'auth':data['auth']}})
    car_owner_db.update_one({'admin_id': data['admin_id']}, {'$set':{'admin_registered_at':timestamp}})

    resp['edited_driver'] = str(car_owner_db.find_one({'admin_id':data['admin_id']}, {'_id':False}))
    return jsonable_encoder(resp)


@app.get('/api/allcardriverlist')
async def on_list(request: Request):
    resp = {'status':'OK'}
    # query and return all registered car drivers
    car_db = mongo_client.car_db
    car_driver_db = car_db.car_driver
    resp['car_drivers'] = list(car_driver_db.find({}, {'_id':False}))
    return jsonable_encoder(resp)


@app.get('/api/allcarownerlist')
async def register(request: Request):
    resp = {'status':'OK'}
    # query and return all registered car owners
    car_db = mongo_client.car_db
    car_owner_db = car_db.car_owner
    resp['car_owners'] = list(car_owner_db.find({}, {'_id':False}))
    return jsonable_encoder(resp)