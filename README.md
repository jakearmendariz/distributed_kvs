# Assignment 4

# Goal
Implement a distributed key-value store that is partition-tolerant, available, and causally consistent. In other words, in the event of a partition, your team’s key-value store is expected to be available, while still providing some consistency–specifically causal consistency.

# Protocols
- Consistent hashing: To distribute requests among shards
- 

## Communicating repliacas
OPTION ONE: make client wait if there is a partition
if len(queue[address]) > 0:
    send(queue) if fails add the newest key_value pair to the queue
        recieve: if len(queue[address]) > 0: return my updates as well. MERGE VECTOR CLOCKS AND STORAGE
    if successful queue[address] = {}

GET request
hey guys do you have the same value as me?
for address in shard: 
    check if queue is empty
    What do you have?

GET/PUT
queue[address][key] = value

OPTION TWO: Continually gossip, ever X miliseconds
Upside, reduce client delay
Downside: increase work during down periods/non partitions

Establishing a total ordering:
    time.time() returns an integer value of ms since 1989. 
        a replica invokes this function it saves a key:value pair in memory
        