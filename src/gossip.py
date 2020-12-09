from apscheduler.schedulers.background import BackgroundScheduler
import time
import atexit
from app import app
from constants import GOSSIP_TIMEOUT
from static import Request, Http_Error, Entry
import kvs
from flask import request

@app.before_first_request
def begin_gossip():
    # app.logger.info(f'Adding a background scheduler for gossip, running every {GOSSIP_TIMEOUT} miliseconds')
    scheduler = BackgroundScheduler()
    scheduler.add_job(func=anti_entropy, trigger="interval", seconds=GOSSIP_TIMEOUT * 0.001)
    scheduler.start()

def anti_entropy():
    # app.logger.info(f'anti_entropy')
    for address in kvs.state.queue:
        if len(kvs.state.queue[address]) > 0:
            response = Request.send_gossip(address, {'address':kvs.state.address, 'queue':kvs.state.queue[address]})
            if response.status_code != 500:
                kvs.state.queue[address].clear()

@app.route('/kvs/gossip', methods=['PUT'])
def gossip_endpoint():
    # app.logger.info(f'gossip recieved from {request.get_json()["address"]}')
    queue = request.get_json()['queue']
    for key in queue.keys():
        if key in kvs.state.storage:
            kvs.state.storage[key] = Entry.max_of_entries(kvs.state.storage[key], queue[key])
        else:
            kvs.state.storage[key] = queue[key]