"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
state.py

Handles the state
"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
from app import app
from hashlib import sha1
import os
import requests
import random
import threading
import copy
import constants

class State():
    def __init__(self): 
        #self.view is the latest view. List of sorted addresses.
        self.view = sorted(os.environ.get('VIEW').split(','))
        #copy of self.view
        self.view_copy = copy.deepcopy(self.view) 
        #self.address is address of the current node.
        self.address = os.environ.get('ADDRESS')
        # Maximum number of replicas each shard should have
        self.repl_factor = os.environ["REPL_FACTOR"]
        #Vector clock data structure
        self.vector_clock = {}
        #Initializing vector clock data structure
        for address in range(len(self.view)):
            self.vector_clock.update({self.view[address]:0})
        # dictionary of all addresses in global view and their shard id's
        self.global_shard_map = {}
        # List of all addresses in local view (shard or cluster) and their shard id's
        self.local_shard_view = [] 
        # Populating global_shard_map (thank you Jake)
        for address in range(len(self.view)):
            shard_id = ((address//int(self.repl_factor)) + 1)
            self.global_shard_map.update({self.view[address]:shard_id})
        # shard_id is the local replica's shard id
        self.shard_id = self.global_shard_map[self.address]
        # Populating local_shard_view
        for address in self.global_shard_map:
            if(self.global_shard_map[address] == self.shard_id):
                self.local_shard_view.append(address)
        #copy of local_shard_view
        self.local_shard_view_copy = copy.deepcopy(self.local_shard_view)
        # self.map stores the hash value to address mapping.
        self.map = {}
        # The number of node replica for one address.
        self.node_replica = 2048
        for address in self.view:
            self.hash_and_store_address(address)
        # The list of total keys in the map.
        self.indices = sorted(self.map.keys())
        # The primary kv store.
        self.storage = {}
    
    def hash_and_store_address(self, address):
        hash = State.hash_key(address)
        for _ in range(self.node_replica):
            self.map[hash] = address
            hash = State.hash_key(hash)
            self.map[hash] = address

    """""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
    vector clock functions
    """""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
    #compares self.vector_clock to incoming_vc
    def vector_clock_comparator(self, incoming_vc):
        vc1_flag = vc2_flag = False

        for x in self.vector_clock.keys():
            if self.vector_clock[x] < incoming_vc[x]:
                vc2_flag = True
            if self.vector_clock[x] > incoming_vc[x]:
                vc1_flag = True
        
        if vc1_flag and not vc2_flag:
            return constants.GREATER_THAN
        elif vc2_flag and not vc1_flag:
            return constants.LESS_THAN
        elif vc1_flag and vc2_flag:
            return constants.CONCURRENT
        else:
            return constants.EQUAL

    """""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
    view change functions
    """""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
    def node_change(self, view):
        app.logger.info("Node change starts: " + str(len(self.map.values())) + " nodes.")
        
        if set(view) == set(self.view):
            app.logger.info("No view change")
            return
        app.logger.info("View changed from " + str(self.view) + " to " + str(view))
        self.add_nodes(set(view) - set(self.view))
        self.delete_nodes(set(self.view) - set(view))
        self.indices = sorted(self.map.keys())
        app.logger.info("Node change complete: " + str(len(self.map.values())) + " nodes.")
    
    def key_migration(self, view):
        app.logger.info("Key migration starts")

        for key in list(self.storage.keys()):
            address = self.maps_to(key)
            if self.address != address:
                requests.put(f'http://{address}/kvs/keys/{key}', json = {"value":self.storage[key]}, headers = {"Content-Type": "application/json"})
                del self.storage[key]
        self.view = sorted(list(view))

    def broadcast_view(self, view, multi_threaded = False):
        addresses = set(sorted(view.split(',')) + self.view)
        # First send node-change to all nodes.
        for address in addresses:
            State.send_node_change(address, view)

        # Second send key-migration to all nodes.
        if not multi_threaded:
            for address in addresses:
                State.send_key_migration(address, view)
        else:
            threads = []
            for address in addresses:
                threads.append(threading.Thread(target=State.send_key_migration, args=(address, view)))
                threads[-1].start()
            for thread in threads:
                thread.join()

    @staticmethod
    def send_node_change(address, view):
        requests.put(f'http://{address}/kvs/node-change', json = {"view":view}, timeout=6, headers = {"Content-Type": "application/json"})

    @staticmethod
    def send_key_migration(address, view):
        requests.put(f'http://{address}/kvs/key-migration', json = {"view":view}, timeout=6, headers = {"Content-Type": "application/json"})

    def add_nodes(self, adding):
        for address in adding:
            self.hash_and_store_address(address)
    
    def delete_nodes(self, deleting):
        if len(deleting) > 0:
            for hash_key in list(self.map.keys()):
                if self.map[hash_key] in deleting:
                    del self.map[hash_key]
    

    """""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
    hash to a node
    """""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
    def maps_to(self, key):
        #binary search the key greater than the key provided
        key_hash = State.hash_key(key)
        #if smallest value seen, or greatest value, this key should be stored in the first node. 
        if self.indices[0] >= key_hash or self.indices[-1] < key_hash:
            return self.map[self.indices[0]]
        l,r = 0, len(self.indices)-2
        # Find the section of this key in the ring.
        while(l < r):
            mid = (l+r)//2
            if self.indices[mid] <= key_hash and self.indices[mid+1] >= key_hash:
                return self.map[self.indices[mid+1]]
            elif self.indices[mid] > key_hash:
                r = mid
            elif self.indices[mid+1] < key_hash:
                l = mid+1
        
        return self.map[self.indices[-1]]
    
    @staticmethod
    def hash_key(key):
        return sha1(key.encode('utf-8')).hexdigest()
