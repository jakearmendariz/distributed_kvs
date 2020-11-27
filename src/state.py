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
        self.view = sorted(os.environ.get('VIEW').split(','))
        self.address = os.environ.get('ADDRESS')
        self.repl_factor = int(os.environ["REPL_FACTOR"])
        
        # SHARD
        # dictionary of all addresses in global view and their shard id's
        self.shard_map = {address:(index//int(self.repl_factor) + 1) for index,address in enumerate(self.view)}
        self.shard_id = self.shard_map[self.address]
        # The number of virtual nodes per node
        self.virtual_map = {}
        for address in self.view:
            self.hash_and_store_address(address)
        self.indices = sorted(self.virtual_map.keys())

        #REPLICA
        self.storage = {}
        self.local_view = [address for address in self.view if self.shard_map[address] == self.shard_id]
        self.vector_clock = {address:0 for address in self.local_view}
        # ask other nodes in shard for their values upon startup
        # self.start_up()
        self.queue = {address:{} for address in self.local_view}

    """""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
    vector clock functions
    """""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
    def start_up(self):
        # Upon startup contact all other replicas in the cluster and appropriate the most up-to-date store and VC
        # by keeping a running max of the VC's that you encounter as you go
        for address in self.view:
            if(address != self.address):
                try:
                    response = requests.get(f'http://{address}/kvs/update', timeout=5).json()
                    version = self.compare_to(response['vector_clock'])
                    if version == constants.LESS_THAN:
                        self.vector_clock = response['vector_clock']
                        self.storage = response['store']
                    elif version == constants.GREATER_THAN:
                        # TODO send the values
                        pass
                    elif version == constants.CONCURRENT:
                        #TODO find the leader, solve for difference
                        pass
                except(requests.exceptions.ConnectTimeout, requests.exceptions.ReadTimeout, requests.exceptions.ConnectionError, requests.exceptions.Timeout ) as _:
                    app.logger.info("server is down")
    
    #compares self.vector_clock to incoming_vc
    def compare_to(self, incoming_vc):
        vc1_flag = vc2_flag = False

        for x in self.vector_clock.keys():
            if self.vector_clock[x] < incoming_vc[x]:
                vc2_flag = True
            elif self.vector_clock[x] > incoming_vc[x]:
                vc1_flag = True
        
        if vc1_flag and not vc2_flag: return constants.GREATER_THAN
        elif vc2_flag and not vc1_flag: return constants.LESS_THAN
        elif vc1_flag and vc2_flag: return constants.CONCURRENT
        else: return constants.EQUAL
    

    """""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
    view change functions
    """""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
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
    
    def node_change(self, view):
        app.logger.info("Node change starts: " + str(len(self.virtual_map.values())) + " nodes.")
        
        if set(view) == set(self.view):
            app.logger.info("No view change")
            return
        app.logger.info("View changed from " + str(self.view) + " to " + str(view))
        self.add_nodes(set(view) - set(self.view))
        self.delete_nodes(set(self.view) - set(view))
        self.indices = sorted(self.virtual_map.keys())
        app.logger.info("Node change complete: " + str(len(self.virtual_map.values())) + " nodes.")

    def key_migration(self, view):
        app.logger.info("Key migration starts")
        self.indices = sorted(self.virtual_map.keys())
        for key in list(self.storage.keys()):
            address = self.maps_to(key)
            if self.address != address:
                requests.put(f'http://{address}/kvs/keys/{key}', json = {"value":self.storage[key]}, headers = {"Content-Type": "application/json"})
                del self.storage[key]
        self.view = sorted(list(view))

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
            for hash_key in list(self.virtual_map.keys()):
                if self.virtual_map[hash_key] in deleting:
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

    """""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
    Forwarding requests
    """""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
    # def forward_to_shard(self, reques)