"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
state.py

contains entire application state. Including storage, mappings, causal data and view
"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
from app import app
from hashlib import sha1
import os
import requests
import copy
import constants
import time
import json
from static import Request, Http_Error, Entry

class State():
    def __init__(self):
        self.view = sorted(os.environ.get('VIEW').split(','))
        self.address = os.environ.get('ADDRESS')
        self.repl_factor = int(os.environ["REPL_FACTOR"])

        # SHARD
        # dictionary of all addresses in global view and their shard id's
        self.shard_map = {address: (index // int(self.repl_factor) + 1) for index, address in enumerate(self.view)}
        self.shard_ids = [str(id) for id in set(self.shard_map.values())]
        if self.address in self.shard_map:
            self.shard_id = self.shard_map[self.address]
        else:
            self.shard_id = -1
        # The number of virtual nodes per node
        self.virtual_map = {}
        for address in self.view:
            self.hash_and_store_address(address)
        self.indices = sorted(self.virtual_map.keys())

        #REPLICA
        self.storage = {}
        self.key_count = 0
        self.local_view = [address for address in self.view if self.shard_map[address] == self.shard_id]
        self.replicas = [address for address in self.local_view if address != self.address]

        self.logical = 0
        # ask other nodes in shard for their values upon startup
        self.queue = {address:{} for address in self.local_view}

    def new_vector_clock(self):
        return {address:0 for address in self.local_view}
    
    def new_causal_context(self):
        logical = {shard_id:0 for shard_id in self.shard_ids}
        logical[str(self.shard_id)] = self.logical
        return {'logical':logical, 'queue':{}, 'view':self.view, 'repl_factor':self.repl_factor}

    def inspect_causal(self, queue):
        for key in queue.keys():
            causal = Entry.compare_entries(self.storage.get(key, {}), queue[key])
            if causal == constants.LESS_THAN:
                self.logical += 1
                if key not in self.storage:self.key_count += 1
                self.storage[key] = Entry.max_of_entries(self.storage.get(key, {}), queue[key])

    """""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
    entry functions
    """""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
    def build_delete_entry(self):
        entry = Entry.build_entry('', 'DELETE', self.address, self.new_vector_clock())
        entry['vector_clock'][self.address] += 1
        return entry

    def build_put_entry(self, value):
        entry = Entry.build_entry(value, 'PUT',  self.address, self.new_vector_clock())
        entry['vector_clock'][self.address] += 1
        return entry

    def update_put_entry(self, value, entry):
        update = self.build_put_entry(value)
        update['vector_clock'] = copy.deepcopy(entry['vector_clock'])
        update['vector_clock'][self.address] += 1
        return update

    def update_delete_entry(self, entry):
        update = self.build_delete_entry()
        update['vector_clock'] = copy.deepcopy(entry['vector_clock'])
        update['vector_clock'][self.address] += 1
        return update

    def storage_contains(self, key):
        return key in self.storage and self.storage[key]['method'] != 'DELETE'

    """""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
    view change functions
    """""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
    def broadcast_view(self, view, repl_factor):
        addresses = set(sorted(view.split(',')) + self.view)
        for address in addresses:
                Request.send_node_change(address, view, repl_factor)
        for address in addresses:
            Request.send_key_migration(address, view)


    def node_change(self, view, repl_factor):
        if set(view) == set(self.view): return
        self.add_nodes(set(view) - set(self.view))
        self.delete_nodes(set(self.view) - set(view))
        self.update_view(view, repl_factor)
        self.logical = 0

    def key_migration(self, view):
        deleting = {address:{} for address in self.view}
        putting = {address:{} for address in self.view}
        # rehash every key, if it belongs in different shard, put else. If in our shard, restart vector clock
        for key in list(self.storage.keys()):
            address = self.maps_to(key)
            shard_id = self.shard_map[address]
            
            if self.shard_id != shard_id:
                if self.storage[key]['method'] != 'DELETE':
                    putting[address][key] = self.storage[key]['value']
                    self.key_count -= 1
                del self.storage[key]
            else:
                self.storage[key]['vector_clock'] = self.new_vector_clock()
                for address in self.replicas:
                    if self.storage[key]['method'] != 'DELETE':
                        putting[address][key] = self.storage[key]
                    else:
                        deleting[address][key] = self.storage[key]
        # send mass storage
        for address, store in putting.items():
            if len(store) > 0:
                if self.shard_map[address] == self.shard_id:
                    Request.put_store(address, store, constants.REPLICA)
                else:
                    Request.put_store(address, store, constants.SHARD)
        # send mass deletion
        for address, store in deleting.items():
            if len(store) > 0:
                if self.shard_map[address] == self.shard_id:
                    Request.delete_store(address, store, constants.REPLICA)
                else:
                    Request.delete_store(address, store, constants.SHARD)

    """""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
    forwarding writes and deletions
    """""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
    # sends a value to a shard, first successful request wins
    def put_to_shard(self, shard_id, key, value, causal_context={'queue':{}, 'logical':0}):
        for i in range(self.repl_factor):
            address = self.view[(shard_id-1)*self.repl_factor + i]
            response = Request.send_put(address, key, value, causal_context)
            if response.status_code != 500:
                payload = response.json()
                payload['address'] = address
                return payload, response.status_code
        # unreachable by TA guarentee at least one node will be available in every shard
        return json.dumps({"error":"Unable to satisfy request", "message":"Error in PUT"}), 503
    
    def put_to_replicas(self, key, entry, causal_context):
        successful_broadcast = True
        for address in self.replicas:
            response = Request.send_put_endpoint(address, key, entry, causal_context)
            status_code = response.status_code
            if status_code == 500:
                self.queue[address][key] = entry
                successful_broadcast = False
            else:
                causal_context['logical'][str(self.shard_id)] = self.logical+1 if causal_context['logical'][str(self.shard_id)] <= self.logical else causal_context['logical'][str(self.shard_id)]
        return successful_broadcast

    # deletes key:value from shard
    def delete_from_shard(self, shard_id, key, causal_context={'queue':{}, 'logical':0}):
        for i in range(self.repl_factor):
            address = self.view[(shard_id-1)*self.repl_factor + i]
            response = Request.send_delete(address, key, causal_context)
            if response.status_code != 500:
                payload = response.json()
                payload['address'] = address
                return payload, response.status_code
        # unreachable
        return json.dumps({"error":"Unable to satisfy request", "message":"Error in DELETE", "causal-context":causal_context}), 503

    def delete_from_replicas(self, key, entry, causal_context):
        successful_broadcast = True
        for address in self.replicas:
            response = Request.send_delete_endpoint(address, key, entry)
            if response.status_code == 500:
                self.queue[address][key] = entry
                successful_broadcast = False
            else:
                causal_context['logical'][str(self.shard_id)] = self.logical+1 if causal_context['logical'][str(self.shard_id)] <= self.logical else causal_context['logical'][str(self.shard_id)]
        return successful_broadcast

    """""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
    view-change function
    """""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
    # Updates all instance variables according to an updated view
    def update_view(self, updated_view, repl_factor):
        self.view = sorted(list(updated_view))
        self.repl_factor = repl_factor
        self.indices = sorted(self.virtual_map.keys())
        self.shard_map = {address:(index//int(self.repl_factor) + 1) for index,address in enumerate(self.view)}
        self.shard_ids = [str(id) for id in set(self.shard_map.values())]
        self.shard_id = self.shard_map.get(self.address, 0)
        self.local_view = [address for address in self.view if self.shard_map[address] == self.shard_id]
        self.replicas = [address for address in self.local_view if address != self.address]

    def add_nodes(self, adding):
        for address in adding:
            self.hash_and_store_address(address)

    def delete_nodes(self, deleting):
        if len(deleting) > 0:
            for hash_key, address in list(self.virtual_map.items()):
                if address in deleting:
                    del self.virtual_map[hash_key]

    """""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
    hash to a node
    """""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
    def maps_to(self, key):
        #binary search the key greater than the key provided
        key_hash = State.hash_key(key)
        #if smallest value seen, or greatest value, this key should be stored in the first node.
        if self.indices[0] >= key_hash or self.indices[-1] < key_hash:
            return self.virtual_map[self.indices[0]]
        l,r = 0, len(self.indices)-2
        # Find the section of this key in the ring.
        while(l < r):
            mid = (l+r)//2
            if self.indices[mid] <= key_hash and self.indices[mid+1] >= key_hash:
                return self.virtual_map[self.indices[mid+1]]
            elif self.indices[mid] > key_hash:
                r = mid
            elif self.indices[mid+1] < key_hash:
                l = mid+1

        return self.virtual_map[self.indices[-1]]

    def hash_and_store_address(self, address):
        hash = State.hash_key(address)
        for _ in range(constants.VIRTUAL_NODE_COUNT):
            self.virtual_map[hash] = address
            hash = State.hash_key(hash)
            self.virtual_map[hash] = address

    @staticmethod
    def hash_key(key):
        return sha1(key.encode('utf-8')).hexdigest()

