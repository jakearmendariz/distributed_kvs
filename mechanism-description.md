# Mechanism Description
## Goal
Implement a distributed key-value store that is partition-tolerant, available, and causally consistent. In other words, in the event of a partition, your team’s key-value store is expected to be available, while still providing some consistency–specifically causal consistency.

## Vocabulary
### Server State
Every server is represented by a combined state that includes:
- view: list of addresses for every server
- local_view: list of addresses in the shard
- replicas: list of addressses - one's own address
- shard_id: personal shard_id
- shard_map: a mapping of address to shard_id
- virtual_map: a mapping of all virtual node locations and a map to their correspodning node address
- vector_clock: vector clock is a map between addresses in local view to their count. Vector clock is updated before acking the client on a succesful PUT or DELETE
- storage: a mapping of all keys in storage to an entry object defining when entry was last updated
- queue: a mapping for all replicas in local_view to a dictionary of {key:entry} pairs defining the missed values needing to be sent to the replica

### Entry
Every value stored is saved as an entry json object: `{'value':value, 'vector_clock':vc_of_server_on_most_recent_update, 'method':POST or DELETE, 'created_at:'timestamp'}`
<br><br>
An entry is greater than, or further in the future of another iff its vector clock is greater or concurrent with a timestamp larger

### Causal Context
Every client can maintain a causual context that will display their most recent operation. The operation will be saved as a entry plus a key so
`'key':{'value':value, 'vector_clock':vc_of_recent_request, 'method':GET or PUT or DELETE, 'created_at:'timestamp'}`

### Consistent Hashing
To distribute values across shards we will use consistent hashing. Every node will have multiple virtual nodes represented by hash values, when a key hashes in the range of an address, it will be sent to that address's shard and be replicated in every node

# Overview
Every node in the server will be initlize it's own view, replicas and shard and virtual map upon creation. Each server is equal to each other in its role as a replica and shard. For all key value requests (PUT, GET, DELETE) the recieving node will map the key to an address by hashing it, then searching through the sorted virtual_map to find the storage address. If it belongs to another shard we will forward the request to `/kvs/keys/key`. But if the key maps to it's own shard, then the node will build an entry for the action (delete or put) and the node will broadcast the entry and the requests causal context to `kvs/key` to each replica inside of the shard, at this endpoint the node will store, delete or retrieve the key:entry pair. If any of the broadcasts fail due to a partition or timeout then we will store the key:entry pair and return it to the client, otherwise there is no need for causal context.

## GET
Get requests are the only request that will not be forwarded to replicas. Upon recieving a get request at an endpoint, the node will check the causal context for the key and its own storage. 
1. if the causal context is empty (or in the past of node) and storage has the key:entry pair
    - return entry
2. if causal context contains the key
    - compare each entry, the entry farter in future overwrites both and is returned to the client
3. if causal context has a logical clock farther in the future
    - return 400 error, it is farther in the future and we don't have the key for causal context. Thus we reject the request and wait for partition to heal or a client to provide more recent context.

### PUT		
Save the request, return as causal context


### DELETE
Complete the request, return as causal context

### View Change
- The view change implementation remains mostly the same in a replicated system as the previously scalable and sharded system in assignment3. The key difference is values are sent (and deleted) iff the shard_id changed, their address owner no longer matters. By the same logic, when a shard adds new addresses, the addresses within a shard must share all of their values with the other nodes that are now responsible for new kvs.
<br><br>
View change is completed in 3 steps<br>

1. node change: tell all other nodes of the update view, they should calculate their new shard_id and find their fellow replicas.
2. key migration: send away all kvs that no longer belong inside a server's shard
3. key-count: count the keys on each server, verify all keys are accounted for and replicated on alive servers

### Shards
If there are n nodes, and a replication factor of r, then there are n/r shards in our distributed system. Each shard will consist of its own data and own map of virtual nodes describing which server (shard) owns each range of keys. Within each shard the data is replicated in every alive node.

## Node Communication

### Forwarding
Send the entry to every server in the local_view. If PUT/DELETE is unsuccessful (whether due to timeout, connection failure or message lost) save inside of the queue to be sent with gossip


### Gossip:
Nodes will 'gossip' between themselves to update each other on missed requests on the queue.

### Sending Gossip
Every X miliseconds a background process will check the queue of every local_address, if non empty send all missed entries. If successful clear queue.

### Receiving gossip:
Gossip is received in one request, but every entry must be examined individually to decide which entry to save/remove from storage.
<br><br>
Loop through every key and entry in the dictionary.<br>
Find the max of storage entry and the gossip entry, store that value