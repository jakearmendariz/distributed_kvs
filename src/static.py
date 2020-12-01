"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
static.py

Holds 3 classes, Entry, Request and Http_Error.

Entry and Request are a collection of related functions with no shared data. Completely static classes

Http_Error is in Request to better model all omission or crash failures as a 500 response
"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
from app import app
import requests
import constants
import time

"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
Entry

Every operation writing to the kvs will be saved as an entrys
"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
class Entry():
    @staticmethod
    def build_entry(value = None, method='PUT', vector_clock={}):
        entry = {}
        entry['value'] = value
        entry['method'] = method
        entry['vector_clock'] = vector_clock
        entry['created_at'] = time.time()
        return entry

    @staticmethod
    def compare_vector_clocks(vc1, vc2):
        vc1_flag = vc2_flag = False

        for x in vc1.keys():
            if vc1[x] < vc2[x]:
                vc2_flag = True
            elif vc1[x] > vc2[x]:
                vc1_flag = True
        
        if vc1_flag and not vc2_flag:
            return constants.GREATER_THAN
        elif vc2_flag and not vc1_flag:
            return constants.LESS_THAN
        elif vc1_flag and vc2_flag:
            return constants.CONCURRENT
        else:
            return constants.EQUAL
    
    @staticmethod
    def vc_pairwise_max(vc1, vc2):
        pass

    @staticmethod
    def compare_entries(entry1, entry2):
        result = Entry.compare_vector_clocks(entry1['vector_clock'], entry2['vector_clock'])
        if result == constants.CONCURRENT or result == constants.EQUAL:
            entry = entry1 if entry1['created_at'] > entry2['created_at'] else entry2
            #TODO pairwise max
            #entry['vector_clock'] = State.pairwise_max(entry1['vector_clock'], entry2['vector_clock'])
            return entry
        elif result == constants.LESS_THAN:
            # entry1 wins
            return entry2
        else:
            return entry1

"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
Request

Contains a series of functions to make requests allowing for errors of the server being down
"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
class Request():
    @staticmethod
    def send_get(address, key):
        try:
            response = requests.get(f'http://{address}/kvs/{key}', timeout=2)
        except(requests.exceptions.ConnectTimeout, requests.exceptions.ReadTimeout, requests.exceptions.ConnectionError, requests.exceptions.Timeout ) as _:
            response = Http_Error(500)
        finally:
            return response
    
    @staticmethod
    def send_put(address, key, value):
        response = None
        try:
            response = requests.put(f'http://{address}/kvs/keys/{key}', json = {'value':value}, timeout=2, headers = {"Content-Type": "application/json"})
        except(requests.exceptions.ConnectTimeout, requests.exceptions.ReadTimeout, requests.exceptions.ConnectionError, requests.exceptions.Timeout ) as _:
            response = Http_Error(500)
        return response
    
    @staticmethod
    def send_delete(address, key):
        try:
            response = requests.delete(f'http://{address}/kvs/keys/{key}', timeout=2)
        except(requests.exceptions.ConnectTimeout, requests.exceptions.ReadTimeout, requests.exceptions.ConnectionError, requests.exceptions.Timeout ) as _:
            response = Http_Error(500)
        finally:
            return response

    @staticmethod
    def send_delete_endpoint(address, key):
        try:
            response = requests.delete(f'http://{address}/kvs/{key}', timeout=2)
        except(requests.exceptions.ConnectTimeout, requests.exceptions.ReadTimeout, requests.exceptions.ConnectionError, requests.exceptions.Timeout ) as _:
            response = Http_Error(500)
        finally:
            return response
    
    @staticmethod
    def send_put_endpoint(address, key, request_json):
        response = None
        try:
            response = requests.put(f'http://{address}/kvs/{key}', json = request_json, timeout=2, headers = {"Content-Type": "application/json"})
        except(requests.exceptions.ConnectTimeout, requests.exceptions.ReadTimeout, requests.exceptions.ConnectionError, requests.exceptions.Timeout ) as _:
            response = Http_Error(500)
        return response
    
    @staticmethod
    def send_get_update(address):
        try:
            response = requests.get(f'http://{address}/kvs/update', timeout=3)
        except(requests.exceptions.ConnectTimeout, requests.exceptions.ReadTimeout, requests.exceptions.ConnectionError, requests.exceptions.Timeout ) as _:
            response = Http_Error(500)
        finally:
            return response

    @staticmethod
    def send_node_change(address, view, repl_factor):
        requests.put(f'http://{address}/kvs/node-change', json = {"view":view, 'repl_factor':repl_factor}, timeout=6, headers = {"Content-Type": "application/json"})

    @staticmethod
    def send_key_migration(address, view):
        requests.put(f'http://{address}/kvs/key-migration', json = {"view":view}, timeout=6, headers = {"Content-Type": "application/json"})

"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
Http_Error

A struct, allows us to view errors properlly
"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
class Http_Error():
    def __init__(self, status_code, msg = "Error"):
        self.status_code = status_code
        self.msg = msg