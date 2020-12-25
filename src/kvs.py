"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
kvs.py

kvs.py accepts inputs on /kvs/keys/<key> endpoints to save, forward and distribute
"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
from app import app
from flask import request
import json
import requests
from state import State
import logging
from static import Request, Http_Error, Entry

global state
@app.before_first_request
def build_state():
    global state
    state = State()

def get_causal_context(request):
    data = request.get_json()
    if data == None: data = {}
    causal_context = data.get('causal-context', {})
    if len(causal_context) == 0 or causal_context['view'] != state.view or causal_context['repl_factor'] != state.repl_factor: 
        causal_context = state.new_causal_context()
    return causal_context
"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
key value store
"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
@app.route('/kvs/keys/<key>', methods=['GET'])
def get(key):
    if state.address not in state.view: return json.dumps({"error":"Unable to satisfy request", "message":"Error in GET"}), 503
    address = state.maps_to(key)
    shard_id = state.shard_map[address]
    causal_context = get_causal_context(request)
    if shard_id == state.shard_id:
        response = Request.send_get(state.address, key, causal_context)
        payload = response.json()
        if 'address' in payload: del payload['address']
        return payload, response.status_code
    else:
        # Attempt to send to every address in a shard, first one that doesn't tine 
        shard_id -= 1
        for i in range(state.repl_factor):
            address = state.view[shard_id*state.repl_factor + i]
            response = Request.send_get(address, key, causal_context)
            if response.status_code != 500:
                return response.json(), response.status_code
        #unreachable due to TA guarentee        
        app.logger.error(f'No requests were successfully forwarded to shard.{shard_id}')
        return json.dumps({"error":"Unable to satisfy request", "message":"Error in GET"}), 503


@app.route('/kvs/keys/<key>', methods=['PUT'])
def put(key):
    data = request.get_json()
    causal_context = get_causal_context(request)
    address = state.maps_to(key)
    shard_id = state.shard_map[address]
    if shard_id == state.shard_id:
        if 'value' not in data:
            return json.dumps({"error":"Value is missing","message":"Error in PUT","causal-context":causal_context}), 400
        if len(key) > 50:
            return json.dumps({"error":"Key is too long","message":"Error in PUT","causal-context":causal_context}), 400
        # if in storage update, else create
        entry = state.update_put_entry(data['value'], state.storage[key]) if key in state.storage else state.build_put_entry(data['value'])
        causal_context['queue'][key] = entry
        successful_broadcast = state.put_to_replicas(key, entry, causal_context)
        if not successful_broadcast:
            causal_context['queue'][key] = entry
        elif key in causal_context['queue']:
            del causal_context['queue'][key]
        # # save on local, return causal context to client
        response = Request.send_put_endpoint(state.address, key, entry, causal_context)
        payload = response.json()
        payload['causal-context'] = causal_context
        return payload, response.status_code
    else:
        # try sending to every node inside of expected shard, first successful quit
        return state.put_to_shard(shard_id, key, data['value'], causal_context)

@app.route('/kvs/keys/<key>', methods=['DELETE'])
def delete(key):
    address = state.maps_to(key)
    shard_id = state.shard_map[address]  
    # get causal context, if empty, initalize
    causal_context = get_causal_context(request)
    # if its in our shard, foward
    if shard_id == state.shard_id:
        entry = state.update_delete_entry(state.storage[key]) if key in state.storage else state.build_delete_entry()
        # forward to replicas
        successful_broadcast = state.delete_from_replicas(key, entry, causal_context)
        if not successful_broadcast: # if a node didn't recieve, save in client
            causal_context['queue'][key] = entry
        elif key in causal_context['queue']: # if every node recieved, delete previous context from client
            del causal_context['queue'][key]
        # send to self
        response = Request.send_delete_endpoint(state.address, key, entry, causal_context)
        payload = response.json()
        payload['causal-context'] = causal_context
        return payload, response.status_code
    else:
        # key belongs to different shard, foward deletion
        return state.delete_from_shard(shard_id, key, causal_context)

