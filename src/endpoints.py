"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
endpoints.py

External and internal endpoints for saving values and retrieving information
"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
import kvs
from app import app
from flask import request
import json
import requests
from state import State
from static import Request, Http_Error, Entry
import time
import constants

"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
Setting values
"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
@app.route('/kvs/<key>', methods=['GET'])
def getter(key):
    data = request.get_json()
    if data == None: data = {}
    causal_context = data.get('causal-context', {})
    if len(causal_context) == 0 or causal_context['view'] != kvs.state.view or causal_context['repl_factor'] != kvs.state.repl_factor: 
        causal_context = kvs.state.new_causal_context()
    queue = causal_context['queue']
    logical = causal_context['logical'][str(kvs.state.shard_id)]
    #logical context, if causal context remembers a higher logical clock, don't return a value
    if logical > kvs.state.logical and key not in causal_context:
        return json.dumps({"error":"Unable to satisfy request","message":"Error in GET", 'causal-context':causal_context}), 400
    elif logical < kvs.state.logical:
        causal_context['logical'][str(kvs.state.shard_id)] = kvs.state.logical
    if key in kvs.state.storage:
        entry = kvs.state.storage[key]
        if key in queue: entry = Entry.max_of_entries(entry, queue[key])
        causal_context['queue'][key] = entry
        if entry['method'] == 'DELETE':
            return json.dumps({"doesExist":False,"error":"Key does not exist","message":"Error in GET", "address":kvs.state.address, 'causal-context':causal_context}), 404
        else:
            return json.dumps({"doesExist":True, "message":"Retrieved successfully", "value": entry['value'], "address":kvs.state.address, 'causal-context':causal_context}), 200 
    else:
        if key in queue and queue[key]['method'] !='DELETE':
            return json.dumps({"doesExist":True, "message":"Retrieved successfully", "value": queue[key]['value'], "address":kvs.state.address, 'causal-context':causal_context}), 200,
        return json.dumps({"doesExist":False,"error":"Key does not exist","message":"Error in GET", "address":kvs.state.address, 'causal-context':causal_context}), 404
        

@app.route('/kvs/<key>', methods=['PUT'])
def putter(key):
    kvs.state.logical += 1
    replace = kvs.state.storage_contains(key)
    if not replace: kvs.state.key_count += 1
    message = "Updated successfully" if replace else "Added successfully"
    status_code = 200 if replace else 201
    data = request.get_json()
    entry = data['entry']
    causal_context = data['causal-context']
    if len(causal_context) == 0 or causal_context['view'] != kvs.state.view or causal_context['repl_factor'] != kvs.state.repl_factor: 
        causal_context = kvs.state.new_causal_context()
    kvs.state.inspect_causal(causal_context['queue'])
    kvs.state.storage[key] = entry
    return json.dumps({"message": message, "replaced": replace}), status_code


@app.route('/kvs/<key>', methods=['DELETE'])
def deleter(key):
    kvs.state.logical += 1
    in_storage = kvs.state.storage_contains(key)
    
    data = request.get_json()
    kvs.state.storage[key] = data['entry']
    causal_context = request.get_json().get('causal-context', {})
    if len(causal_context) == 0 or causal_context['view'] != kvs.state.view or causal_context['repl_factor'] != kvs.state.repl_factor: 
        causal_context = kvs.state.new_causal_context()
    kvs.state.inspect_causal(causal_context['queue'])
    if in_storage:
        kvs.state.key_count -= 1
        return json.dumps({"doesExist": True, "message": "Deleted successfully"}), 200
    else:
        if key in causal_context['queue'] and causal_context['queue'][key]['method'] != 'DELETE':
            return json.dumps({"doesExist": True, "message": "Deleted successfully"}), 200
        return json.dumps({"doesExist": False, "error": "Key does not exist", "message": "Error in DELETE"}), 404


"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
Information endpoints
"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""

@app.route('/kvs/key-count', methods=['GET'])
def count():
    return json.dumps({"message":"Key count retrieved successfully","key-count":kvs.state.key_count, 
        "shard-id": str(kvs.state.shard_id)}), 200, 

# Returns an array of string ids
@app.route('/kvs/shards', methods=['GET'])
def get_shard_membership():
    return json.dumps({"message": "Shard membership retrieved successfully", "shards": kvs.state.shard_ids}), 200

# Get shard information given a shard id.
@app.route('/kvs/shards/<id>', methods=['GET'])
def get_shard_information(id):
    shard_id = int(id) - 1
    key_count = 0
    for i in range(kvs.state.repl_factor):
        address =kvs.state.view[shard_id*kvs.state.repl_factor + i]
        response = requests.get(f'http://{address}/kvs/key-count')
        key_count = max(key_count, response.json()['key-count'])
    return json.dumps({"message": "Shard information retrieved successfully", "shard-id": id, 
        "key-count": key_count, "replicas":kvs.state.view[shard_id*kvs.state.repl_factor:(shard_id+1)*kvs.state.repl_factor]}), 200


"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
send all of storage
"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
@app.route('/kvs/update', methods=["GET"])
def my_state():
    payload = {"store":kvs.state.storage, "vector_clock":kvs.state.vector_clock}
    return json.dumps(payload), 200

@app.route('/kvs/clear-storage', methods=["PUT"])
def clear_storage():
    kvs.state.storage = {}
    kvs.state.key_count = 0
    return json.dumps({'message':'storage cleared successfully'}), 200
