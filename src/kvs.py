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
    # Upon startup contact all other replicas in the cluster
    # and appropriate the most up-to-date store and VC
    # by keeping a running max of the VC's
    # that you encounter as you go
    for address in range(len(state.local_shard_view)):
        addr       = state.local_shard_view[address]
        local_addr = state.address
        if(addr != local_addr):
            try:
                response = requests.get(f'http://{addr}/kvs/update', timeout=5)
                incoming_store = response.json()["store"]
                incoming_VC    = response.json()["VC"]
                verdict        = state.VC_comparator(state.return_VC(), incoming_VC)
                if(verdict == state.LESS_THAN):
                    state.replace_VC(incoming_VC)
                    state.storage.clear()
                    state.storage.update(incoming_store)
            except(requests.exceptions.ConnectTimeout, requests.exceptions.ReadTimeout, 
            requests.exceptions.ConnectionError, requests.exceptions.Timeout ) as e:
                state.local_shard_view_copy.remove(addr)
                state.view_copy.remove(addr)


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

        #TODO
        # determine logic for how to deal with causal consistency 
        # (how/when to update vector clock)
        # (how/when to add data to local storage)
        # This is the hard part.  We need everyone's brains!  I'm too stupid!

        replace = key in state.storage
        message = "Updated successfully" if replace else "Added successfully"
        status_code = 200 if replace else 201
        state.storage[key] = data["value"]
        return json.dumps({"message":message,"replaced":replace}), status_code
    else:
        app.logger.info("This is from the else case of the add() funct")
        try:
            response = requests.put(f'http://{address}/kvs/keys/{key}', json = request.get_json(), timeout=6, headers = {"Content-Type": "application/json"})
            proxy_response = response.json()
            proxy_response['address'] = address
            return proxy_response, response.status_code
        except(requests.exceptions.ConnectTimeout, requests.exceptions.ReadTimeout, 
        requests.exceptions.ConnectionError, requests.exceptions.Timeout ) as e:
            #we may want to have a running list of up nodes and down nodes, so 
            #I added the below lines of code to this except block
            #if it turns out we don't use these copies of the lists
            # then we can just get rid of the lines below
            if(address in state.local_shard_view_copy):
                state.local_shard_view_copy.remove(address)
            if(address in state.view_copy):
                state.view_copy.remove(address)
        return json.dumps({"error":"Unable to satisfy request", "message":"Error in PUT"}), 503


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

"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
replica comms
"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
@app.route('/kvs/update', methods=["GET"])
def return_replica_data():
    global state
    payload = {"store":state.storage, "VC":state.return_VC()}
    return json.dumps(payload), 200



