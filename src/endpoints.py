import kvs
from app import app
from flask import request
import json
import requests
from state import State

@app.route('/kvs/<key>', methods=['GET'])
def getter(key):
    if key in kvs.state.storage:
        return json.dumps({"doesExist":True, "message":"Retrieved successfully", "value": kvs.state.storage[key]['value']}), 200, 
    return json.dumps({"doesExist":False,"error":"Key does not exist","message":"Error in GET"}), 404
    

@app.route('/kvs/<key>', methods=['PUT'])
def putter(key):
    data = request.get_json()
    replace = key in kvs.state.storage
    message = "Updated successfully" if replace else "Added successfully"
    status_code = 200 if replace else 201
    kvs.state.storage[key] = State.build_entry(data['value'], 'POST', kvs.state.vector_clock)
    kvs.state.vector_clock[kvs.state.address] += 1
    return json.dumps({"message":message,"replaced":replace}), status_code


@app.route('/kvs/<key>', methods=['DELETE'])
def deleter(key):
    if key in kvs.state.storage:
        kvs.state.vector_clock[kvs.state.address] += 1
        del kvs.state.storage[key]
        return json.dumps({"doesExist":True,"message":"Deleted successfully"}), 200
    return json.dumps({"doesExist":False,"error":"Key does not exist","message":"Error in DELETE"}), 404