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


global state
@app.before_first_request
def build_state():
    global state
    state = State()
    app.logger.info("This is state.view from build_state():")
    app.logger.info(state.view)
    app.logger.info("This is replication factor from build_state():") 
    app.logger.info(state.repl_factor)
    app.logger.info("This is shard count from build_state():")
    app.logger.info(state.shard_count)
    app.logger.info("This is globalShardIdDict from build_state():")
    app.logger.info(state.global_shard_id_dict)
    app.logger.info("This is self.VC from build_state():")
    app.logger.info(str(state.VC.returnVC()))
    app.logger.info("This is the local shard view from build_state():")
    app.logger.info(str(state.local_shard_view))

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
    return json.dumps({"message": "View change successful","shards":shards}), 200

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
    if address == state.address:
        if key in state.storage:
            return json.dumps({"doesExist":True, "message":"Retrieved successfully", "value": state.storage[key]}), 200, 
        return json.dumps({"doesExist":False,"error":"Key does not exist","message":"Error in GET"}), 404
    else:
        response = requests.get(f'http://{address}/kvs/keys/{key}')
        if response.status_code == 200:
            proxy_response = response.json()
            proxy_response['address'] = address
            return proxy_response, response.status_code
        print("error in get")
        return json.dumps({"doesExist":False,"error":"Key does not exist","message":"Error in GET", "address": address}), 404
    

@app.route('/kvs/keys/<key>', methods=['PUT'])
def add(key):
    global state
    app.logger.info("This is state.view from add() funct: ")
    app.logger.info(str(state.view))
    data = request.get_json()
    if "value" not in data: return json.dumps({"error":"Value is missing","message":"Error in PUT"}), 400
    if len(key) > 50 : return json.dumps({"error":"Key is too long","message":"Error in PUT"}), 400
    address = state.maps_to(key)
    if address == state.address:
        replace = key in state.storage
        message = "Updated successfully" if replace else "Added successfully"
        status_code = 200 if replace else 201
        state.storage[key] = data["value"]
        return json.dumps({"message":message,"replaced":replace}), status_code
    else:
        app.logger.info("This is from the else case of the add() funct")
        response = requests.put(f'http://{address}/kvs/keys/{key}', json = request.get_json(), timeout=6, headers = {"Content-Type": "application/json"})
        proxy_response = response.json()
        proxy_response['address'] = address
        return proxy_response, response.status_code


@app.route('/kvs/keys/<key>', methods=['DELETE'])
def delete(key):
    global state
    address = state.maps_to(key)
    if address == state.address:
        if key in state.storage:
            del state.storage[key]
            return json.dumps({"doesExist":True,"message":"Deleted successfully"}), 200
        return json.dumps({"doesExist":False,"error":"Key does not exist","message":"Error in DELETE"}), 404
    else:
        response = requests.delete(f'http://{address}/kvs/keys/{key}', timeout=6, headers = {"Content-Type": "application/json"})
        proxy_response = response.json()
        proxy_response['address'] = address
        return proxy_response, response.status_code
