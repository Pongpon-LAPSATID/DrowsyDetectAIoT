import os
import sys
import logging
from datetime import datetime
import json

from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from linebot.v3.webhook import WebhookHandler
from linebot.v3.exceptions import (
    InvalidSignatureError
)
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage
)
from linebot.v3.webhooks import (
    MessageEvent,
    TextMessageContent,
    FollowEvent,
    UnfollowEvent
)

import paho.mqtt.client as mqtt

from urllib.error import HTTPError, URLError
from urllib.request import urlopen
from urllib.request import Request as urllib_Request

# logging configuration
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# mqtt config
mqtt_broker = os.getenv('MQTT_BROKER', None)
if mqtt_broker is None:
    logging.error('MQTT_BROKER undefined.')
    sys.exit(1)
mqtt_port = os.getenv('MQTT_PORT', None)
if mqtt_port is None:
    logging.error('MQTT_PORT undefined.')
    sys.exit(1)

# MQTT data sources; for publishing CMD message
MQTT_CMD_TOPIC = os.getenv('MQTT_CMD_TOPIC', None)
if MQTT_CMD_TOPIC is None:
    logging.error('MQTT_CMD_TOPIC undefined.')
    sys.exit(1)

# linebot configuration
channel_secret = os.getenv('LINE_CHANNEL_SECRET', None)
liff_id = os.getenv('USER_ID_FIND_LIFF_ID', None) # change LIFF_ID here
if channel_secret is None:
    print('Specify LINE_CHANNEL_SECRET as environment variable.')
    sys.exit(1)
channel_access_token = os.getenv('LINE_ACCESS_TOKEN', None)
if channel_access_token is None:
    print('Specify LINE_ACCESS_TOKEN as environment variable.')
    sys.exit(1)
if liff_id is None:
    print('Specify LIFF_ID as environment variable.')
    sys.exit(1)
configuration = Configuration(
    access_token=channel_access_token
)

# API URL
#user_api_url = os.getenv('USER_API_URL', None)
#user_api_url = f"http://host.docker.internal:{os.getenv('USER_API_PORT', None)}"
user_api_url = f"{os.getenv('USER_API_URL', None)}{os.getenv('USER_API_PORT', None)}"
if user_api_url is None:
    logging.error('Failed to retrieve USER_API_URL')
    sys.exit(1)

#dev_api_url = f"http://host.docker.internal:{os.getenv('DEV_API_PORT', None)}"
dev_api_url = f"{os.getenv('DEV_API_URL', None)}{os.getenv('DEV_API_PORT', None)}"
if dev_api_url is None:
    logging.error('Failed to retrieve DEV_API_URL')
    sys.exit(1)


# start instance
app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

handler = WebhookHandler(channel_secret)


@app.post("/callback")
async def handle_callback(request: Request):
    signature = request.headers['X-Line-Signature']
    # get request body as text
    body = await request.body()
    body = body.decode()
    #body = request.get_data(as_text=True)
    #app.logger.info("Request body: " + body)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail="Invalid signature")
    return 'OK'

# code for web UI


@app.get('/')
async def liff_ui(request: Request):
    return templates.TemplateResponse(
        request=request, name="FindUserID.html", context={"LIFF_ID": liff_id}
    )

# code to handle Follow event


@handler.add(FollowEvent)
def handle_follow_event(event):
    pass

# code to handle text messages


@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    text = event.message.text
    user_id = event.source.user_id
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        print(f'text: {text}')
        target_dev = text.split()[-1]
        print(f'target_dev: {target_dev}')
        try:
            if text.startswith('status'): # status dev_id or status all
                print(f'Admin requests to check status of dev_id: {target_dev}')

                if target_dev.lower() == 'all':
                    # request /api/alldevlog
                    print('case 1-1')
                    data, statuscode = fetch_data_get(os.path.join(dev_api_url, 'api/alldevstatus'))
                    print(f'statuscode: {statuscode}')
                    if statuscode != 200:
                        resp = TextMessage(text=f'{statuscode}: Internal system/API error')
                        print(f'{statuscode} Error; Dev API Failed. Data failed to be posted to registration endpoint.')
                        line_bot_api.reply_message(
                            ReplyMessageRequest(
                                reply_token=event.reply_token,
                                messages=[resp]
                            )
                        )
                        return None

                    if data['log'] == []:
                        print(f'No data exists in device_log database.')
                        resp = TextMessage(text=f'No data exists in device_log database.')
                        line_bot_api.reply_message(
                            ReplyMessageRequest(
                                reply_token=event.reply_token,
                                messages=[resp]
                            )
                        )
                        return None
                    
                    print('checkpoint')
                    resp = TextMessage(text=f'Here is the status of {target_dev}:\n{data["log"]}')
                    print('/api/alldevstatus requested successfully')
                    
                else:
                    # request /api/devlog/dev_id
                    print('case 1-2')
                    data, statuscode = fetch_data_get(os.path.join(dev_api_url, f'api/devstatus/{target_dev}'))
                    
                    if statuscode != 200:
                        resp = TextMessage(text=f'{statuscode}: Internal system/API error')
                        print(f'{statuscode} Error; Dev API Failed. Data failed to be posted to registration endpoint.')
                        line_bot_api.reply_message(
                            ReplyMessageRequest(
                                reply_token=event.reply_token,
                                messages=[resp]
                            )
                        )
                        return None

                    if data['log'] == []:
                        print(f'{target_dev} does not exist in device_log database.')
                        resp = TextMessage(text=f'{target_dev} does not exist in device_log database.')
                        line_bot_api.reply_message(
                            ReplyMessageRequest(
                                reply_token=event.reply_token,
                                messages=[resp]
                            )
                        )
                        return None
                    
                    print('checkpoint')
                    resp = TextMessage(text=f'Here is the status of {target_dev}:\n{data["log"]}')
                    print('/api/devstatus requested successfully')
                    
            
            elif text.startswith('activate'): # activate dev_id or activate all
                target_dev = text.split()[-1]
                
                if target_dev.lower() == "all":
                    print('case 2-1')
                    # request /api/activateall
                    data, statuscode = fetch_data_get(os.path.join(dev_api_url, 'api/activateall'))
                    
                    if statuscode != 200:
                        resp = TextMessage(text=f'{statuscode}: Internal system/API error')
                        print(f'{statuscode} Error; Dev API Failed. Data failed to be posted to registration endpoint.')
                        line_bot_api.reply_message(
                            ReplyMessageRequest(
                                reply_token=event.reply_token,
                                messages=[resp]
                            )
                        )
                        return None

                    if data['CMD_updated'] == []:
                        print(f'No data exists in device_log database.')
                        resp = TextMessage(text=f'No data exists in device_log database.')
                        line_bot_api.reply_message(
                            ReplyMessageRequest(
                                reply_token=event.reply_token,
                                messages=[resp]
                            )
                        )
                        return None

                    # LINE Bot reply message
                    resp = TextMessage(text=f'All dev_ids are activated !')
                    print('All dev_ids are activated !')
                     
                else:
                    print('case 2-2')
                    # request /api/activate/dev_id
                    data, statuscode = fetch_data_get(os.path.join(dev_api_url, f'api/activate/{target_dev}'))
                    
                    if statuscode != 200:
                        resp = TextMessage(text=f'{statuscode}: Internal system/API error')
                        print(f'{statuscode} Error; Dev API Failed. Data failed to be posted to registration endpoint.')
                        line_bot_api.reply_message(
                            ReplyMessageRequest(
                                reply_token=event.reply_token,
                                messages=[resp]
                            )
                        )
                        return None

                    if data['CMD_updated'] == []:
                        print(f'{target_dev} does not exist in device_log database.')
                        resp = TextMessage(text=f'{target_dev} does not exist in device_log database.')
                        line_bot_api.reply_message(
                            ReplyMessageRequest(
                                reply_token=event.reply_token,
                                messages=[resp]
                            )
                        )
                        return None
                    
                    resp = TextMessage(text=f'dev_id: {target_dev} is activated.')
                    print('API requested successfully')
                    
                    
            elif text.startswith('deactivate'): # activate dev_id or activate all
                target_dev = text.split()[-1]
                
                if target_dev.lower() == "all":
                    print('case 3-1')
                    # request /api/activateall
                    data, statuscode = fetch_data_get(os.path.join(dev_api_url, 'api/deactivateall'))
                    
                    if statuscode != 200:
                        resp = TextMessage(text=f'{statuscode}: Internal system/API error')
                        print(f'{statuscode} Error; Dev API Failed. Data failed to be posted to registration endpoint.')
                        line_bot_api.reply_message(
                            ReplyMessageRequest(
                                reply_token=event.reply_token,
                                messages=[resp]
                            )
                        )
                        return None

                    if data['CMD_updated'] == []:
                        print(f'No data exists in device_log database.')
                        resp = TextMessage(text=f'No data exists in device_log database.')
                        line_bot_api.reply_message(
                            ReplyMessageRequest(
                                reply_token=event.reply_token,
                                messages=[resp]
                            )
                        )
                        return None

                    # LINE Bot reply message
                    resp = TextMessage(text=f'All dev_ids are deactivated !')
                    print('All dev_ids are deactivated !')
                     
                else:
                    print('case 3-2')
                    # request /api/deactivate/dev_id
                    data, statuscode = fetch_data_get(os.path.join(dev_api_url, f'api/deactivate/{target_dev}'))
                    
                    if statuscode != 200:
                        resp = TextMessage(text=f'{statuscode}: Internal system/API error')
                        print(f'{statuscode} Error; Dev API Failed. Data failed to be posted to registration endpoint.')
                        line_bot_api.reply_message(
                            ReplyMessageRequest(
                                reply_token=event.reply_token,
                                messages=[resp]
                            )
                        )
                        return None

                    if data['CMD_updated'] == []:
                        print(f'{target_dev} does not exist in device_log database.')
                        resp = TextMessage(text=f'{target_dev} does not exist in device_log database.')
                        line_bot_api.reply_message(
                            ReplyMessageRequest(
                                reply_token=event.reply_token,
                                messages=[resp]
                            )
                        )
                        return None
                    
                    resp = TextMessage(text=f'dev_id: {target_dev} is deactivated.')
                    print('API requested successfully')
                    
            else:
                resp = TextMessage(text="We apologize for inconvenience. The acceptable LINE message commands are:\n 1. status all, status dev_id\n2. activate all, activate dev_id\n3. deactivate all, deactivate dev_id\n\nOr, click Menu to add/edit database in admin's sites")

        except Exception as e:
            resp = TextMessage(text=f'Error; Exception: {e}')
            print(f'Error; Exception: {e}')

        # reply message via LINE Bot
        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[resp]
            )
        )

def make_request(url, data=None, headers={}):
    #request = Request(url, headers=headers or {}, data=data)
    request = urllib_Request(url, data=data, headers=headers)
    try:
        with urlopen(request, timeout=10) as response:
            print(f'status_code: {response.status}') # print status code
            return response.read(), response
    except HTTPError as e:
        print(f'HTTP Error: {e}')
    except URLError as e:
        print(f'URL Error: {e}')
    except TimeoutError:
        print('Request timed out')
    except Exception as e:
        print(f'Error occurred during HTTP Request: {e}')

def fetch_data_get(url, headers={}):
    body, response = make_request(url, headers=headers)
    print(f'body: {body}')
    print(f'response: {response}')
    #dec_body = body.decode('utf-8')
    #print(f'dec_body: {dec_body}')
    #data = json.loads(dec_body)
    data = json.loads(body, strict=False)
    print(f'data: {data}')

    return data, response.getcode()

def fetch_data_post(url:str, post_dict:dict, headers={}):
    json_str = json.dumps(post_dict)
    post_data = json_str.encode('utf-8')
    body, response = make_request(
        url,
        data = post_data,
        headers = headers
    )
    print(f'body: {body}')
    print(f'response: {response}')
    #dec_body = body.decode('utf-8')
    #print(f'dec_body: {dec_body}')
    #data = json.loads(dec_body)
    data = json.loads(body, strict=False)
    print(f'data: {data}')

    return data, response.getcode()
