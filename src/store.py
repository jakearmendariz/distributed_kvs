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
storing packages of values
"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
@app.route('/kvs/view-change/store', methods=['PUT'])
def put_store():
    data = request.get_json()
    if data['type'] == 'shard':
        for key, value in data['store'].items():
            data['store'][key] = kvs.state.build_put_entry(value)
        # forward update to every replica
        for address in kvs.state.local_view:
            Request.put_store(address, data['store'], 'replica')
        return json.dumps({'message':'success'}), 200
    elif data['type'] == 'replica':
        for key, entry in data['store'].items():
            if not kvs.state.storage_contains(key):
                kvs.state.key_count += 1
            kvs.state.storage[key] = entry
        return json.dumps({'message':'success'}), 200
    else:
        return json.dumps({'message':'unreachable'}), 500


@app.route('/kvs/view-change/store', methods=['DELETE'])
def delete_store():
    data = request.get_json()
    if data['type'] == 'shard':
        for key, _value in data['store'].items():
            # build entry
            data['store'][key] = kvs.state.build_delete_entry()
        # forward update to every replica
        for address in kvs.state.local_view:
            Request.delete_store(address, data['store'], 'replica')
        return json.dumps({'message':'success'}), 200
    elif data['type'] == 'replica':
        for key, _value in data['store'].items():
            if kvs.state.storage_contains(key):
                kvs.state.key_count -= 1
                kvs.state.storage[key] = kvs.state.update_delete_entry(kvs.state.storage[key])
            else:
                kvs.state.storage[key] = kvs.state.build_delete_entry()
        return json.dumps({'message':'success'}), 200
    else:
        return json.dumps({'message':'unreachable'}), 500