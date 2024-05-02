import os
import sys
import logging
from pymongo import MongoClient

import schedule
import time

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

def hb_check():
    # call the databases
    dev_db = mongo_client.dev_db
    dev_log = dev_db.device_log
    dev_logs = list(dev_log.find({}, {'dev_id': True}))
    dev_id_list = [device['dev_id'] for device in dev_logs]
    #dev_latestms_dict = dict.fromkeys(dev_id_list, 0) # initialize all latest_hb_ms at 0 for each dev_id

    # if no heartbeat after 5 sec from the latest heartbeat, status --> offline
    for devid in dev_id_list:
        #latest_hb_ms = dev_latestms_dict[devid]
        latest_hb_ms = dev_log.find_one({'dev_id': devid}, {'_id': False})['latest_hb_ms']
        current_ms = time.time()
        print(f'current_ms: {current_ms}')
        if ((current_ms - latest_hb_ms) >= 5):
            dev_log.update_one({'dev_id': devid}, {'$set':{'status':'offline'}})
            print(f'dev_id: {devid} || status: "offline" || latest_hb_ms = {latest_hb_ms}')
        else:
            dev_log.update_one({'dev_id': devid}, {'$set':{'status':'online'}})
            print(f'dev_id: {devid} || status: "online" || latest_hb_ms = {latest_hb_ms}')


schedule.every(5).seconds.do(hb_check)

while True:
    schedule.run_pending()
    time.sleep(1)