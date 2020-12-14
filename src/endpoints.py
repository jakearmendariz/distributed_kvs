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
view change
"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
@app.route('/kvs/view-change', methods=['PUT'])
def view_change():
    view_str = request.get_json()['view']
    replica_factor = request.get_json().get('repl-factor', kvs.state.repl_factor)
    app.logger.info("Start broadcast view change: " + str(kvs.state.view))
    kvs.state.broadcast_view(view_str, replica_factor)

    shards = {}
    for address in kvs.state.view:
        response = Request.send_get(address, 'key-count', {})
        if response.status_code == 500: continue
        shard_id = response.json()["shard-id"]
        key_count = response.json()['key-count']
        if shard_id in shards:
            key_count = min(key_count, shards[shard_id]['key-count'])
            shards[shard_id]['key-count'] = key_count
        else:
            replicas = [address for address in kvs.state.view if shard_id == str(kvs.state.shard_map[address])]
            shards[shard_id] = {"shard-id": shard_id, "key-count": key_count, "replicas": replicas}
    return json.dumps({"message": "View change successful","shards":list(shards.values())}), 200

@app.route('/kvs/node-change', methods=['PUT'])
def node_change():
    kvs.state.node_change(request.get_json()['view'].split(','), int(request.get_json()['repl-factor']))
    return json.dumps({"message":"node change succeed"}), 201

@app.route('/kvs/key-migration', methods=['PUT'])
def key_migration():
    kvs.state.key_migration(request.get_json()['view'].split(','))
    return json.dumps({"message":"key migration succeed"}), 201

"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
Setting values
"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
@app.route('/kvs/<key>', methods=['GET'])
def getter(key):
    causal_context = request.get_json().get('causal-context', {'queue':{}, 'logical':0})
    if len(causal_context) == 0: causal_context = {'queue':{}, 'logical':0}
    logical = causal_context['logical']
    queue = causal_context['queue']
    if logical > kvs.state.logical and key not in causal_context:
        return json.dumps({"error":"Unable to satisfy request","message":"Error in GET"}), 400
    elif logical < kvs.state.logical:
        causal_context['logical'] = kvs.state.logical
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
    kvs.state.vector_clock[kvs.state.address] += 1
    kvs.state.logical += 1
    replace = kvs.state.storage_contains(key)
    if not replace: kvs.state.key_count += 1
    message = "Updated successfully" if replace else "Added successfully"
    status_code = 200 if replace else 201
    data = request.get_json()
    entry = data['entry']
    causal_context = data['causal-context']['queue']
    # For every key, update the value with the current causal context
    for cc_key in causal_context.keys():
        if Entry.compare_entries(kvs.state.storage.get(cc_key, {}), causal_context[cc_key]) == constants.LESS_THAN:
            kvs.state.logical += 1
            if key not in kvs.state.storage: kvs.state.key_count += 1
            kvs.state.storage[cc_key] = Entry.max_of_entries(kvs.state.storage.get(cc_key, {}), causal_context[cc_key])
    kvs.state.storage[key] = entry
    return json.dumps({"message": message, "replaced": replace}), status_code


@app.route('/kvs/<key>', methods=['DELETE'])
def deleter(key):
    kvs.state.vector_clock[kvs.state.address] += 1
    kvs.state.logical += 1
    in_storage = kvs.state.storage_contains(key)
    
    data = request.get_json()
    kvs.state.storage[key] = data['entry']
    causal_context = request.get_json().get('causal-context', {})
    if len(causal_context) == 0: causal_context = {'queue':{}, 'logical':0}
    causal_context = data['causal-context']['queue']

    # For every key, update the value with the current causal context
    for cc_key in causal_context.keys():
        if Entry.compare_entries(kvs.state.storage.get(cc_key, {}), causal_context[cc_key]) == constants.LESS_THAN:
            kvs.state.logical += 1
            if cc_key not in kvs.state.storage: kvs.state.key_count += 1
            kvs.state.storage[cc_key] = Entry.max_of_entries(kvs.state.storage.get(cc_key, {}), causal_context[cc_key])
    if in_storage:
        kvs.state.key_count -= 1
        return json.dumps({"doesExist": True, "message": "Deleted successfully"}), 200
    else:
        if key in causal_context and causal_context[key]['method'] != 'DELETE':
            return json.dumps({"doesExist": True, "message": "Deleted successfully"}), 200
        return json.dumps({"doesExist": False, "error": "Key does not exist", "message": "Error in DELETE", "address":kvs.state.address}), 404


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
