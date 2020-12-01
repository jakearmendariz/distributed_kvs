import kvs
from app import app
from flask import request
import json
import requests
from state import State
from static import Request, Http_Error, Entry

"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
view change
"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
@app.route('/kvs/view-change', methods=['PUT'])
def view_change():
    view_str = request.get_json()['view']
    replica_factor = request.get_json().get('repl_factor', kvs.state.repl_factor)
    app.logger.info("Start broadcast view change: " + str(kvs.state.view))
    kvs.state.broadcast_view(view_str, replica_factor)
    app.logger.info("Completed broadcast view change: " + str(kvs.state.view))

    shards = {}
    app.logger.info("started kvs key count") 
    for address in kvs.state.view:
        response = Request.send_get(address, 'key-count')
        if response.status_code == 500: continue
        shard_id = response.json()["shard-id"]
        key_count = response.json()['key-count']
        if shard_id in shards: 
            key_count = max(key_count, shards[shard_id]['key-count'])
            shards[shard_id]['key-count'] = key_count
        else:
            replicas = [address for address in kvs.state.view if shard_id == kvs.state.shard_map[address]]
            shards[shard_id] = {"shard-id": shard_id, "key-count": key_count, "replicas": replicas}
    return json.dumps({"message": "View change successful","shards":list(shards.values())}), 200

@app.route('/kvs/node-change', methods=['PUT'])
def node_change():
    app.logger.info(request.get_json()['view'])
    kvs.state.node_change(request.get_json()['view'].split(','), int(request.get_json()['repl_factor']))
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
    if key in kvs.state.storage:
        return json.dumps({"doesExist": True, "message": "Retrieved successfully", "value": kvs.state.storage[key]['value']}), 200, 
    return json.dumps({"doesExist": False, "error": "Key does not exist", "message": "Error in GET"}), 404
    

@app.route('/kvs/<key>', methods=['PUT'])
def putter(key):
    data = request.get_json()
    replace = key in kvs.state.storage
    message = "Updated successfully" if replace else "Added successfully"
    status_code = 200 if replace else 201
    kvs.state.storage[key] = Entry.build_entry(data['value'], 'PUT', kvs.state.vector_clock)
    kvs.state.vector_clock[kvs.state.address] += 1
    return json.dumps({"message": message, "replaced": replace}), status_code


@app.route('/kvs/<key>', methods=['DELETE'])
def deleter(key):
    if key in kvs.state.storage:
        kvs.state.vector_clock[kvs.state.address] += 1
        del kvs.state.storage[key]
        return json.dumps({"doesExist": True, "message": "Deleted successfully"}), 200
    return json.dumps({"doesExist": False, "error": "Key does not exist", "message": "Error in DELETE"}), 404


"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
Information endpoints
"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""

@app.route('/kvs/key-count', methods=['GET'])
def count():
    return json.dumps({"message":"Key count retrieved successfully","key-count":len(kvs.state.storage.keys()), 
        "shard-id": kvs.state.shard_id}), 200, 

# Returns an array of string ids
@app.route('/kvs/shards', methods=['GET'])
def get_shard_membership():
    return json.dumps({"message": "Shard membership retrieved successfully", "shards": kvs.state.shard_ids}), 200

# Get shard information given a shard id.
@app.route('/kvs/shards/<id>', methods=['GET'])
def get_shard_information(shard_id):
    shard_id -= 1
    key_count = 0
    for i in range(kvs.state.repl_factor):
            address =kvs.state.view[shard_id*kvs.state.repl_factor + i]
            response = requests.get(f'http://{address}/kvs/key-count')
            key_count = max(key_count, response.json()['key-count'])
    return json.dumps({"message": "Shard information retrieved successfully", "shard-id": id+1, 
        "key-count": key_count, "replicas":kvs.state.view[shard_id*kvs.state.repl_factor:(shard_id+1)*kvs.state.repl_factor]}), 200


"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
send all of storage
"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
@app.route('/kvs/update', methods=["GET"])
def my_state():
    payload = {"store":kvs.state.storage, "vector_clock":kvs.state.vector_clock()}
    return json.dumps(payload), 200