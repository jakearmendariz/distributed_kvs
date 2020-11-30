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
import time

class State():
    def __init__(self): 
        self.view = sorted(os.environ.get('VIEW').split(','))
        self.address = os.environ.get('ADDRESS')
        self.repl_factor = int(os.environ["REPL_FACTOR"])
        
        # SHARD
        # dictionary of all addresses in global view and their shard id's
        self.shard_map = {address:(index//int(self.repl_factor) + 1) for index,address in enumerate(self.view)}
        self.shard_ids = [str(id) for id in set(self.shard_map.values())]
        self.shard_id = self.shard_map[self.address]
        # The number of virtual nodes per node
        self.virtual_map = {}
        for address in self.view:
            self.hash_and_store_address(address)
        self.indices = sorted(self.virtual_map.keys())

        #REPLICA
        self.storage = {}
        self.local_view = [address for address in self.view if self.shard_map[address] == self.shard_id]
        self.replicas = [address for address in self.local_view if address != self.address]
        self.vector_clock = {address:0 for address in self.local_view}
        # ask other nodes in shard for their values upon startup
        # self.start_up()
        self.queue = {address:{} for address in self.local_view}

        app.logger.info(f'\n\nnode:{self.address} is on shard {self.shard_id}\n\n')
    """""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
    vector clock functions
    """""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
    def start_up(self):
        # Upon startup contact all other replicas in the cluster and appropriate the most up-to-date store and VC
        # by keeping a running max of the VC's that you encounter as you go
        for address in self.view:
            if address == self.address:
                continue
            try:
                response = requests.get(f'http://{address}/kvs/update', timeout = 5).json()
                version = State.compare_vector_clocks(self.vector_clock, response['vector_clock'])
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

    def compare_entries(self, entry1, entry2):
        result = State.compare_vector_clocks(entry1['vector_clock'], entry2['vector_clock'])
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


    # every entry in storage needs to have a a dictionary defining what it is (needs method)
    @staticmethod
    def build_entry(value = None, method='PUT', vector_clock={}):
        entry = {}
        entry['value'] = value
        entry['method'] = method
        entry['vector_clock'] = vector_clock
        entry['created_at'] = time.time()
        return entry
    

    """""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
    view change functions
    """""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
    def broadcast_view(self, view, repl_factor, multi_threaded = False):
        addresses = set(sorted(view.split(',')) + self.view)
        # First send node-change to all nodes.
        for address in addresses:
            State.send_node_change(address, view, repl_factor)

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
    
    def node_change(self, view, repl_factor):
        app.logger.info("Node change starts: " + str(len(self.virtual_map.values())) + " nodes.")
        if set(view) == set(self.view):
            app.logger.info("No view change")
            return
        app.logger.info("View changed from " + str(self.view) + " to " + str(view))
        self.add_nodes(set(view) - set(self.view))
        self.delete_nodes(set(self.view) - set(view))
        self.update_view(view, repl_factor)
        app.logger.info("Node change complete: " + str(len(self.virtual_map.values())) + " nodes.")

    def key_migration(self, view):
        app.logger.info("Key migration starts")
        for key in list(self.storage.keys()):
            address = self.maps_to(key)
            if self.address != address:
                requests.put(f'http://{address}/kvs/keys/{key}', json = {"value":self.storage[key]}, headers = {"Content-Type": "application/json"})
                del self.storage[key]

    # Updates all instance variables according to an updated view
    def update_view(self, updated_view, repl_factor):
        self.view = sorted(list(updated_view))
        self.repl_factor = repl_factor
        self.indices = sorted(self.virtual_map.keys())
        self.shard_map = {address:(index//int(self.repl_factor) + 1) for index,address in enumerate(self.view)}
        self.shard_id = self.shard_map.get(self.address, 0)
        self.local_view = [address for address in self.view if self.shard_map[address] == self.shard_id]
        self.replicas = [address for address in self.local_view if address != self.address]
    

    @staticmethod
    def send_node_change(address, view, repl_factor):
        requests.put(f'http://{address}/kvs/node-change', json = {"view":view, 'repl_factor':repl_factor}, timeout=6, headers = {"Content-Type": "application/json"})

    @staticmethod
    def send_key_migration(address, view):
        requests.put(f'http://{address}/kvs/key-migration', json = {"view":view}, timeout=6, headers = {"Content-Type": "application/json"})

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
