"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
gossip.py

Starts gossip every 2.3 seconds. Contains the gossip function and endpoint
"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
from apscheduler.schedulers.background import BackgroundScheduler
import time
from app import app
import constants
from static import Request, Http_Error, Entry
import kvs
from flask import request
import json

@app.before_first_request
def begin_gossip():
    scheduler = BackgroundScheduler()
    scheduler.add_job(func=anti_entropy, trigger="interval", seconds=constants.GOSSIP_TIMEOUT)
    scheduler.start()

def anti_entropy():
    for address in kvs.state.queue:
        if len(kvs.state.queue[address]) > 0:
            response = Request.send_gossip(address, {'address':kvs.state.address, 'queue':kvs.state.queue[address]})
            if response.status_code != 500:
                kvs.state.queue[address].clear()

@app.route('/kvs/gossip', methods=['PUT'])
def gossip_endpoint():
    queue = request.get_json()['queue']
    for key in queue.keys():
        if key in kvs.state.storage:
            kvs.state.storage[key] = Entry.max_of_entries(kvs.state.storage[key], queue[key])
            if queue['method'] == 'DELETE':
                kvs.state.key_count -= 1
        else:
            kvs.state.storage[key] = queue[key]
            if queue['method'] == 'POST':
                kvs.state.key_count += 1
    return json.dumps({'message':'gossip complete'}), 200