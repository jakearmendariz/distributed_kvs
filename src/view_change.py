import kvs
from app import app
from flask import request
import json
import requests
from state import State
from static import Request, Http_Error, Entry
import time
import constants

@app.route('/kvs/view-change/store', methods=['PUT'])
def put_store():
    data = request.get_json()
    # app.logger.info(f'\n\data store\ntype:{data["type"]} \nstore:{data["store"]}\n\n\n')
    if data['type'] == 'shard':
        for key, value in data['store'].items():
            # build entry
            # data['store'][key] = kvs.state.update_put_entry(value, kvs.state.storage[key]) if key in kvs.state.storage else kvs.state.build_put_entry(data['value'])
            data['store'][key] = kvs.state.build_put_entry(value)
        # forward update to every replica
        for address in kvs.state.local_view:
            Request.put_store(address, data['store'], 'replica')
        return json.dumps({'message':'success'}), 200
    elif data['type'] == 'replica':
        for key, entry in data['store'].items():
            if not kvs.state.storage_contains(key):
                kvs.state.key_count += 1
            # kvs.state.storage[key] = kvs.state.update_put_entry(value['value'], kvs.state.storage[key]) if key in kvs.state.storage else kvs.state.build_put_entry(value)
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
            # data['store'][key] = kvs.state.update_delete_entry(kvs.state.storage[key]) if key in kvs.state.storage else kvs.state.build_delete_entry()
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