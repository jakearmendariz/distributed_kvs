# Assignment 4
Team: Dorothy, Joshua, Jake, Julian

# Design
## Goal
Implement a distributed key-value store that is partition-tolerant, available, and causally consistent. In other words, in the event of a partition, your team’s key-value store is expected to be available, while still providing some consistency–specifically causal consistency.

## Vocabulary
### Server State
Every server is represented by a combined state that includes:
- view: list of addresses for every server
- local_view: list of addresses in the shard
- shard_id: personal shard_id
- shard_map: a mapping of address to shard_id
- virtual_map: a mapping of all virtual node locations and a map to their correspodning node address
- vector_clock: vector clock is a map between addresses in local view to their count. Vector clock is updated before acking the client on a succesful PUT or DELETE
- storage: a mapping of all keys in storage to an entry object defining when entry was last updated
- queue: a mapping for all replicas in local_view to a dictionary of {key:entry} pairs defining the missed values needing to be send to the replica

### Entry
Every value stored is saved as an entry json object: `{'value':value, 'vector_clock':vc_of_server_on_most_recent_update, 'method':POST or DELETE, 'created_at:'timestamp'}`
<br><br>
An entry is greater than, or further in the future of another iff its vector clock is greater or concurrent with a timestamp larger

### Causal Context
Every client can maintain a causual context that will display their most recent operation. The operation will be saved as a entry plus a key so
`{'key':key, 'value':value, 'vector_clock':vc_of_recent_request, 'method':GET or POST or DELETE, 'created_at:'timestamp'}`

### Consistent Hashing
To distribute values across shards we will use consistent hashing. Every node will have multiple virtual nodes represented by hash values, when a key hashes in the range of an address, it will be sent to that address's shard and be replicated in every node

## Types of Requests
### GET
NOTE: To see if a key exists in storage, a server must check inside dictionary and verify the entry.method == 'PUT'. If most recent entry is 'DELETE', then 404

1. causal context is emtpy
    - return the entry associated with key or 404 error
2. casual context is in the past of server
    - return the entry in storage
3. casual context is in the future/concurrent and most recent request displays the same key
    - compare server's entry to the causal context, return the greater of the two entries
4. casual context is in the future/concurrent and is talking about a different key.
    - server cannot handle request, it doesn't matter if we it does not know what happened in the future `{'error': 'Unable to satisfy request', 'message': 'Error in GET'}, 400`


### PUT		
1. causal context is emtpy
    - store the entry, return it as causal context
2. casual context is in the past of server
    - store the entry, return it as causal context
3. casual context is in the future/concurrent and most recent request displays the same key
    - store clients request in the storage, with pairwise max of client's and servers vector_clocks
4. casual context is in the future/concurrent and is talking about a different key.
    - store clients request in the storage, with pairwise max of client's and servers vector_clocks


### DELETE
1. causal context is emtpy
    - store the entry as a deletion, return it as causal context
2. casual context is in the past of server
    - store the entry as a deletion, return it as causal context
3. casual context is in the future/concurrent and most recent request displays the same key
    - store clients request in the storage as deleltion, with pairwise max of client's and servers vector_clocks
4. casual context is in the future/concurrent and is talking about a different key.
    - store clients request in the storage as deletion, with pairwise max of client's and servers vector_clocks

### View Change
- TODO

### Shards
- TODO

## Node Communication

### Forwarding
Send the entry to every server in the local_view. If PUT/DELETE is unsuccessful (whether due to timeout, connection failure or message lost) save inside of the queue to be sent with gossip


### Gossip:
Nodes will 'gossip' between themselves to update each other on missed requests on the queue.

### Sending Gossip
Every X miliseconds a background process will check the queue of every local_address, if non empty send all missed entries. If successful clear queue.

## Receiving gossip:
Gossip is received in one request, but every entry must be examined individually to decide which entry to save/remove from storage.
<br><br>
Loop through every key and entry in the array.<br>
If an entry is in the future, then use it's value. <br>
If they are concurrent, find pairwise max and use the timestamp to dictate the future.