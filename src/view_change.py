from kvs import state
from app import app
from flask import request
import json
import requests
from state import State
from static import Request, Http_Error, Entry
import time
import constants

@app.route('/kvs/store', methods=['PUT'])
def put(key):
    data = request.get_json()
    if data['type'] == 'shard':
        for key, value in data['store'].items():
            # build entry
            data['store'][key] = state.update_put_entry(value, state.storage[key]) if key in state.storage else state.build_put_entry(data['value'])
        # forward update to every replica
        for address in state.replicas:
            Request.put_keys(address, data['store'], 'replica')
        return json.dumps({'message':'success'}), 200
    elif data['type'] == 'replica':
        for key, value in data['store'].items():
            if not state.storage_contains(key):
                state.key_count += 1
            state.storage[key] = state.update_put_entry(value, state.storage[key]) if key in state.storage else state.build_put_entry(value)
        return json.dumps({'message':'success'}), 200


@app.route('/kvs/store', methods=['DELETE'])
def delete(key):
    data = request.get_json()
    if data['type'] == 'shard':
        for key, _value in data['store'].items():
            # build entry
            data['store'][key] = state.update_delete_entry(state.storage[key]) if key in state.storage else state.build_delete_entry()
        # forward update to every replica
        for address in state.replicas:
            Request.delete_keys(address, data['store'], 'replica')
        return json.dumps({'message':'success'}), 200
    elif data['type'] == 'replica':
        for key, _value in data['store'].items():
            if state.storage_contains(key):
                state.key_count -= 1
                state.storage[key] = state.update_delete_entry(state.storage[key])
            else:
                state.storage[key] = state.build_delete_entry()
        return json.dumps({'message':'success'}), 200