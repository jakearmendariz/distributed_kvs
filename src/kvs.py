"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
kvs.py

kvs.py accepts inputs on /kvs/<key> to store, retrieve and delete values
"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
from app import app
from flask import request
import json
import requests
from state import State
import logging
import sys
import _thread
import copy


global state
@app.before_first_request
def build_state():
    global state
    state = State()

"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
view change
"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
@app.route('/kvs/view-change', methods=['PUT'])
def view_change():
    global state
    view_str = request.get_json()['view']
    app.logger.info("Start broadcast view change: " + str(state.view))
    state.broadcast_view(view_str)
    app.logger.info("Completed broadcast view change: " + str(state.view))

    shards = []
    app.logger.info("started kvs key count") 
    for address in state.view:
        app.logger.info(address)
        if address == state.address:
            app.logger.info("self" + address)
            shards.append({"address":state.address, "key-count":len(state.storage)})
        else:
            app.logger.info("others" + address)
            response = requests.get(f'http://{address}/kvs/key-count') 
            shards.append({"address":address, "key-count":response.json()['key-count']})
    return json.dumps({"message": "View change successful","states":shards}), 200

@app.route('/kvs/node-change', methods=['PUT'])
def node_change():
    global state
    app.logger.info(request.get_json()['view'])
    state.node_change(request.get_json()['view'].split(','))
    return json.dumps({"message":"node change succeed"}), 201

@app.route('/kvs/key-migration', methods=['PUT'])
def key_migration():
    global state
    state.key_migration(request.get_json()['view'].split(','))
    return json.dumps({"message":"key migration succeed"}), 201

@app.route('/kvs/key-count', methods=['GET'])
def count():
    global state
    return json.dumps({"message":"Key count retrieved successfully","key-count":len(state.storage.keys())}), 200, 

"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
key value store
"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""

@app.route('/kvs/keys/<key>', methods=['GET'])
def get(key):
    global state
    address = state.maps_to(key)
    shard_id = state.shard_map[address]
    if shard_id == state.shard_id:
        # TODO verify causual consistency from request context
        if key in state.storage:
            return json.dumps({"doesExist":True, "message":"Retrieved successfully", "value": state.storage[key]}), 200, 
        return json.dumps({"doesExist":False,"error":"Key does not exist","message":"Error in GET"}), 404
    else:
        # Attempt to send to every address in a shard, first one that doesn't tine 
        for i in range(state.repl_factor):
            address = state.view[shard_id*state.repl_factor + i]
            response = send_get(address, key)
            if response.status_code != 500:
                return response.json(), response.status_code
        app.logger.error(f'No requests were successfully forwarded to shard.{shard_id}')
        return json.dumps({"doesExist":False,"error":"Key does not exist","message":"Error in GET", "address": address}), 404

# Handles errors when server is down
def send_get(address, key):
    try:
        response = requests.get(f'http://{address}/kvs/{key}', timeout=2)
    except(requests.exceptions.ConnectTimeout, requests.exceptions.ReadTimeout, requests.exceptions.ConnectionError, requests.exceptions.Timeout ) as _:
        response = {'status_code': 500}
    finally:
        return response

@app.route('/kvs/keys/<key>', methods=['PUT'])
def put(key):
    global state
    data = request.get_json()
    if "value" not in data: return json.dumps({"error":"Value is missing","message":"Error in PUT"}), 400
    if len(key) > 50 : return json.dumps({"error":"Key is too long","message":"Error in PUT"}), 400
    address = state.maps_to(key)
    shard_id = state.shard_map[address]
    if shard_id == state.shard_id:
        # TODO determine logic for how to deal with causal consistency 
        # Send a PUT request to store data for every replica
        self_response = None
        for i in range(state.repl_factor):
            address = state.view[shard_id*state.repl_factor + i]
            response = send_put(address, key, request.get_json())
            if address == state.address:
                self_response = response
            status_code = response.status_code
            if status_code != 200 and status_code != 201:
                state.queue[address][key] = data['value']
        return self_response.json(), self_response.status_code
    else:
        # try sending to every node inside of shard, first successful quit
       for i in range(state.repl_factor):
            address = state.view[shard_id*state.repl_factor + i]
            response = send_put_global(address, key, request.get_json(), shard = True)
            status_code = response.status_code
            if status_code == 200 or status_code == 201:
                return response.json(), status_code       
        return json.dumps({"error":"Unable to satisfy request", "message":"Error in PUT"}), 503

# Handles errors, helps when forwarding to dead nodes
# By default this will send to a non forwarding endpoint (a replica)
def send_put(address, key, request_json, shard = False):
    try:
        if not shard:
            response = requests.put(f'http://{address}/kvs/{key}', json = request_json(), timeout=2, headers = {"Content-Type": "application/json"})
        else:
            response = requests.put(f'http://{address}/kvs/keys/{key}', json = request_json(), timeout=2, headers = {"Content-Type": "application/json"})
    except(requests.exceptions.ConnectTimeout, requests.exceptions.ReadTimeout, requests.exceptions.ConnectionError, requests.exceptions.Timeout ) as _:
        response = {'status_code': 500}
    finally:
        return response

@app.route('/kvs/keys/<key>', methods=['DELETE'])
def delete(key):
    global state
    address = state.maps_to(key)
    shard_id = state.shard_map[address]    
    if shard_id == state.shard_id:
        # Tell every other replica to delete
        for replica_address in set(state.view[shard_id*state.repl_factor:(shard_id+1)*state.repl_factor])- state.address:
            requests.delete(f'http://{replica_address}/kvs/keys/{key}', timeout=2, headers = {"Content-Type": "application/json"})
        # Delete from personal storage
        if key in state.storage:
            del state.storage[key]
            return json.dumps({"doesExist":True,"message":"Deleted successfully"}), 200
        return json.dumps({"doesExist":False,"error":"Key does not exist","message":"Error in DELETE"}), 404
    else:
        for i in range(state.repl_factor):
            address = state.view[shard_id*state.repl_factor + i]
            response = requests.delete(f'http://{address}/kvs/keys/{key}', timeout=2, headers = {"Content-Type": "application/json"})
        return response.json(), response.status_code

"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
state comms
"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
@app.route('/kvs/update', methods=["GET"])
def my_state():
    global state
    payload = {"store":state.storage, "vector_clock":state.vector_clock()}
    return json.dumps(payload), 200



