"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
kvs.py

kvs.py accepts inputs on /kvs/<key> to store, retrieve and delete values
"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
from app import app
from flask import request
import json
import requests
from state import State, Http_Error
import logging
import sys
import _thread
import time
from static import Request, Http_Error, Entry

global state
@app.before_first_request
def build_state():
    global state
    state = State()

"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
key value store
"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
@app.route('/kvs/keys/<key>', methods=['GET'])
def get(key):
    address = state.maps_to(key)
    shard_id = state.shard_map[address]
    if shard_id == state.shard_id:
        # TODO verify causual consistency from request context
        if key in state.storage:
            return json.dumps({"doesExist":True, "message":"Retrieved successfully", "value": state.storage[key]['value']}), 200, 
        return json.dumps({"doesExist":False,"error":"Key does not exist","message":"Error in GET"}), 404
    else:
        # Attempt to send to every address in a shard, first one that doesn't tine 
        shard_id -= 1
        for i in range(state.repl_factor):
            address = state.view[shard_id*state.repl_factor + i]
            response = Request.send_get(address, key)
            if response.status_code != 500:
                return response.json(), response.status_code
        app.logger.error(f'No requests were successfully forwarded to shard.{shard_id}')
        return json.dumps({"doesExist":False,"error":"Key does not exist","message":"Error in GET", "address": address}), 404


@app.route('/kvs/keys/<key>', methods=['PUT'])
def put(key):
    data = request.get_json()
    if 'value' not in data:
        app.logger.info(f'request json data:{data}')
        return json.dumps({"error":"Value is missing","message":"Error in PUT"}), 400
    if len(key) > 50:
        return json.dumps({"error":"Key is too long","message":"Error in PUT"}), 400

    address = state.maps_to(key)
    app.logger.info(''.join(state.shard_map.keys()))
    shard_id = state.shard_map[address]
    if shard_id == state.shard_id:
        for address in state.replicas:
            response = Request.send_put_endpoint(address, key, request.get_json())
            status_code = response.status_code
            if status_code == 500:
                state.vector_clock[address] += 1
            else:
                state.queue[address][key] = Entry.build_entry(data['value'], 'PUT', state.vector_clock)
        response = Request.send_put_endpoint(state.address, key, request.get_json())
        return response.json(), response.status_code
    else:
        # try sending to every node inside of expected shard, first successful quit
        return state.put_to_shard(shard_id, key, data['value'])

@app.route('/kvs/keys/<key>', methods=['DELETE'])
def delete(key):
    address = state.maps_to(key)
    shard_id = state.shard_map[address]  
    if shard_id == state.shard_id:
        for replica_adddress in state.replicas:
            response = Request.send_delete_endpoint(replica_adddress, key)
            if response.status_code == 500:
                state.queue[replica_adddress][key] = Entry.build_entry(method='DELETE', vector_clock=state.vector_clock)
            else:
                state.vector_clock[replica_adddress] += 1
        # Delete from personal storage
        response = Request.send_delete_endpoint(state.address, key)
        if response.status_code == 500:
            return json.dumps({"error":"Unable to satisfy request", "message":"Error in DELETE"}), 503
        return response.json(), response.status_code
    else:
        shard_id -= 1
        for i in range(state.repl_factor):
            address = state.view[shard_id*state.repl_factor + i]
            response = Request.send_delete(address, key)
            if response.status_code != 500:
                return response.json(), response.status_code
        return json.dumps({"error":"Unable to satisfy request", "message":"Error in DELETE"}), 503

