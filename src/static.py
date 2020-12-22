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
    def build_entry(value, method, address, vector_clock):
        entry = {}
        entry['value'] = value
        entry['method'] = method
        entry['address'] = address
        entry['vector_clock'] = vector_clock
        entry['created_at'] = int(time.time())
        return entry
    
    @staticmethod
    def compare_vector_clocks(vc1, vc2):
        if len(vc1) == 0 and len(vc2) == 0: return constants.EQUAL
        elif len(vc1) == 0: return constants.LESS_THAN
        elif len(vc2) == 0: return constants.GREATER_THAN
        elif set(vc1.keys()) != set(vc2.keys()): return constants.MISMATCH
        vc1_flag = vc2_flag = False

        for x in vc1.keys():
            if vc1[x] < vc2[x]:
                vc2_flag = True
            elif vc1[x] > vc2[x]:
                vc1_flag = True
        if len(vc1) > len(vc2): vc1_flag = True
        if len(vc1) < len(vc2): vc2_flag = True 
        
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
        vc = {}
        for address in vc1.keys():
            vc[address] = max(vc1[address], vc2[address])
        return vc

    @staticmethod
    def compare_entries(entry1, entry2):
        if len(entry1) == 0: return constants.GREATER_THAN
        if len(entry2) == 0: return constants.LESS_THAN
        result = Entry.compare_vector_clocks(entry1['vector_clock'], entry2['vector_clock'])
        if result == constants.CONCURRENT:
            if entry1['created_at'] > entry2['created_at']:
                return constants.GREATER_THAN
            elif entry1['created_at'] < entry2['created_at']:
                return constants.LESS_THAN
            else:
                return constants.GREATER_THAN if entry1['address'] > entry2['address'] else constants.LESS_THAN
        else:
            return result

    @staticmethod
    def max_of_entries(entry1, entry2):
        if len(entry1) == 0: return entry2
        if len(entry2) == 0: return entry1
        result = Entry.compare_vector_clocks(entry1['vector_clock'], entry2['vector_clock'])
        if result == constants.CONCURRENT or result == constants.MISMATCH:
            entry = None
            if entry1['created_at'] > entry2['created_at']:
                entry = entry1
            elif entry1['created_at'] < entry2['created_at']:
                entry = entry2
            else:
                entry =  entry1 if entry1['address'] > entry2['address'] else entry2
            if result == constants.CONCURRENT:
                entry['vector_clock'] = Entry.vc_pairwise_max(entry1['vector_clock'], entry2['vector_clock'])
            # elif mismatch use the up to date vector clock
            return entry
        elif result == constants.LESS_THAN:
            return entry2
        elif result == constants.GREATER_THAN: # greater than
            return entry1
        else: # equal so entry1 and entry2 should have the same value
            return entry1

"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
Request

Contains a series of functions to make requests allowing for errors of the server being down
"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
class Request():
    @staticmethod
    def send_get(address, key,causal_context):
        response = None
        try: response = requests.get(f'http://{address}/kvs/{key}', json = {'causal-context':causal_context}, timeout=2)
        except: response = Http_Error(500)
        finally: return response
    
    @staticmethod
    def send_put(address, key, value, causal_context={}):
        response = None
        try: response = requests.put(f'http://{address}/kvs/keys/{key}', json = {'value':value, 'causal-context':causal_context}, timeout=2, headers = {"Content-Type": "application/json"})
        except: response = Http_Error(500)
        finally: return response
    
    @staticmethod
    def send_delete(address, key, causal_context={}):
        response = None
        try: response = requests.delete(f'http://{address}/kvs/keys/{key}', json = {'causal-context':causal_context}, timeout=2)
        except: response = Http_Error(500)
        finally: return response

    @staticmethod
    def send_delete_endpoint(address, key, entry, causal_context={}):
        response = None
        try: response = requests.delete(f'http://{address}/kvs/{key}',json = {'causal-context':causal_context, 'entry':entry}, timeout=2)
        except: response = Http_Error(500)
        finally: return response
    
    @staticmethod
    def send_put_endpoint(address, key, entry, causal_context={}):
        response = None
        try: response = requests.put(f'http://{address}/kvs/{key}', json = {'entry':entry,'causal-context':causal_context}, timeout=2, headers = {"Content-Type": "application/json"})
        except: response = Http_Error(500)
        finally: return response
    
    @staticmethod
    def send_get_update(address):
        response = None
        try: response = requests.get(f'http://{address}/kvs/update', timeout=3)
        except: response = Http_Error(500)
        finally: return response
    
    @staticmethod
    def send_gossip(address, request_json):
        response = None
        try: response = requests.put(f'http://{address}/kvs/gossip', json = request_json, timeout=1, headers = {"Content-Type": "application/json"})
        except: response = Http_Error(500)
        finally: return response


    @staticmethod
    def send_node_change(address, view, repl_factor):
        response = None
        try: response = requests.put(f'http://{address}/kvs/node-change', json = {"view":view, 'repl-factor':repl_factor}, timeout=6, headers = {"Content-Type": "application/json"})
        except: response = Http_Error(500)
        finally: return response

    @staticmethod
    def send_key_migration(address, view):
        response = None
        try: response = requests.put(f'http://{address}/kvs/key-migration', json = {"view":view}, timeout=4, headers = {"Content-Type": "application/json"})
        except: response = Http_Error(500)
        finally: return response

    @staticmethod
    def put_store(address, store, _type):
        response = None
        try: response = requests.put(f'http://{address}/kvs/view-change/store', json = {"type":_type, "store":store}, timeout=3, headers = {"Content-Type": "application/json"})
        except: response = Http_Error(500)
        finally: return response

    @staticmethod
    def delete_store(address, store, _type):
        response = None
        try: response = requests.delete(f'http://{address}/kvs/view-change/store', json = {"type":_type, "store":store}, timeout=3, headers = {"Content-Type": "application/json"})
        except: response = Http_Error(500)
        finally: return response

"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
Http_Error

A struct, allows us to view errors properlly
"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
class Http_Error():
    def __init__(self, status_code, msg = "Error"):
        self.status_code = status_code
        self.msg = msg