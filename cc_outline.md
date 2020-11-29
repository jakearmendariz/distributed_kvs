 establish some shorthand:
 
VCcc  = vector clock from request’s causal context.
VCL   = vector clock local, or local vector clock (vector clock for the local replica itself)
VCLK = vector clock in the local store that is attached to the same key as VCcc (the key from the client request’s causal context, or from the miss dictionary that is associated with a gossip update being received by a replica from another replica in the shard).
VCWK = vector clock in the local store associated with the key that the client (or other replica if the request is a forwarded request) is trying to access.
VCRK = vector clock in the local store associated with the key that the client is trying to read

For PUT requests:
		
	If the key that the client is attempting to write to is not present in the local store and the client request’s causal context is empty, increment local position in VCL.  Create timestamp.  Store the key-value pair from the client request, VCL, and timestamp in the following form:

{“key”:{“value”:<value>, “vc”:<VCL>, “ts”:<timestamp>}}

	Return this very same dictionary above for the client to maintain as causal context.

	If the key that the client is attempting to write to is present in the local store, and the client request’s causal context is empty, increment local position in VCL.  Then VCWK = pairwise_max(VCL, VCWK).  Create timestamp.  Store the key-value pair from the client request, new VCWK, and timestamp in the store in the following form:

{“key”:{“value”:<value>, “vc”:<VCWK>, “ts”:<timestamp>}}

	Return this very same dictionary above for the client to maintain as causal context.

	If the key that the client is attempting to write to is not present in the local store and the client request’s causal context is not empty, increment local position in VCL.  Then VCWK = pairwise_max(VCL, VCcc).  Create timestamp.  Store key-value pair from client request, VCWK, and timestamp in the local store in the following form:
{“key”:{“value”:<value>, “vc”:<VCWK>, “ts”:<timestamp>}}

Return this very same dictionary above for the client to maintain as causal context

	If the key that the client is attempting to write to is present in the store and the client request’s causal context is not empty, increment the local position in the VCL.  Then VCWK = pairwise_max(VCcc, VCWK).  Create timestamp.  Store the key-value pair from the client request, the timestamp, and new VCWK in the local store in the following form:

{“key”:{“value”:<value>, “vc”:<VCWK>, “ts”:<timestamp>}}

Return the very same dictionary above for the client to maintain as causal context.

Forwarding:

	Obviously, any time a request is stored in the local store, that request data must be forwarded to the other replicas in the shard.  If, when attempting to forward a write to the other replicas in the shard, it is discovered that another replica is down (unresponsive), that write will be buffered in a local "miss dictionary" in the following form:

{<address_of_down_replica>: [{“key”:{"value"<value>, "vc":<VCWK>, “ts":<timestamp>,}}]}

	This “miss dictionary" will be of the overall following form:

{{<address_of_down_replica_1>:”VCL”:<VCL>, “miss\_list”:[{"missed\_key\_1":{"value":<value>, "vc":<VCWK1>,”ts”:<timestamp1>}}, {missed\_key\_2":{"value":<value>, "vc":<VCWK2>, "ts”:<timestamp2>}}, …, {“missed\_key\_n":{"value”:<value>, “vc”:<VCWKn>, “ts”:<timestamp\_n>}}]}, {<address_of_down_replica_2>:”VCL”:<VCL>, “miss\_list”:[{"missed\_key\_1":{"value":<value>, "vc":<VCWK1>,”ts”:<timestamp1>}}, {missed\_key\_2":{"value":<value>, "vc":<VCWK2>, "ts”:<timestamp2>}}, …, {missed\_key\_n":{"value”:<value>, “vc”:<VCWKn>, “ts”:<timestamp_n>}}]}, …, {<address_of_down_replica_n>:”VCL”:<VCL>, “miss\_list”: [{"missed\_key\_1":{"value":<value>, "vc":<VCWK1>,”ts”:<timestamp1>}}, {missed\_key\_2":{"value":<value>, "vc":<VCWK2>, "ts”:<timestamp2>}}, …, {missed\_key\_n":{"value”:<value>, “vc”:<VCWKn>, “ts”:<timestamp_n>}}]}}

As you can see, this is a dictionary in which each member is a list of dictionaries.  Parent\_Dictionary(address\_of\_down\_replica\_dictionary(list(individual\_dictionaries\_for\_each\_miss)))

Also note that the “VCL” for each “address\_of\_down\_replica” is not to be inserted until the time that the “miss list” is actually sent (so as to insure that the receiving replica gets the most recent form of the VCL, of course).

For GET requests:

If the key is present in the local store, and the client request’s causal context is empty, increment the local position in the VCL.  Return the key-value pair that the client is requesting along with the VCRK and the timestamp associated with the requested key in the local store in the following form:

{“key”:{“value”:<value>, “vc”:<VCRK>, “ts”:<timestamp>}}

If the key is not present in the local store and the client request’s causal context is empty, return the following: 

{“error”: “Unable to satisfy request”, “message”: “Error in GET”}, 400

If the key is not present in the local store, and the client request’s causal context is not empty, check to see if the key that the client has in its causal context is the same as the key it is requesting access to.  If they are one and same key, simply return the client’s causal context back to it in the following form:

{“key”:{“value”<value>, “vc”:<VCcc>, “ts”:<timestamp>}}

However, if they are not one and the same key, return the following:

{“error”: “Unable to satisfy request”, “message”: “Error in GET”}, 400
	
	If the key is present in the local store and the client request’s causal context is not empty, compare VCcc to VCRK.  If VCcc > VCRK (client is in the future relative to requested key and shouldn’t be able to read the past) then return the following:

	{“error”: “Unable to satisfy request”, “message”: “Error in GET”}, 500
	
	However, if VCcc <= VCRK (client is in the past relative to requested key, it’s fine to let them read the future) return the requested key-value pair, timestamp associated with the requested key in the local store, and the VCcc in the following form:

	{“key”:{“value”:<value>, “vs”:<VCcc>, “ts”:<timestamp>}}

Gossip:

	Sending the gossip
	
	Each replica will iteratively go through their “miss dictionary” and send the respective “miss list” to the appropriate address.  A function that performs this action will run every “x” milliseconds or half second, or whatever time interval seems most appropriate.  

Upon discovering that a replica previously thought to be down is now back up and has received the gossip update successfully, the address associated with that replica in the “miss dictionary” will be wiped clean (until it is discovered that replica has gone down again – at that point the miss list for that replica will begin to build again in the local “miss dictionary”).

This “gossip” will be sent to a different endpoint; not the endpoint associated with the standard “PUT” operations.

Receiving the gossip:

	Upon receiving a gossip update from another replica in the shard, the local replica will iterate through the “miss queue” and for each key it examines, it will first set the VCL = pairwise_max(VCL, VCL_from_gossip).
  
	If the key is not present in the local store, it will simply store the miss in the local store in its received form, i.e.;

	{“key”:{“value”:<value>,  “vc”:<VCcc>, “ts”:<timestamp>}}

where, in this case, VCcc is simply the vector clock associated with the particular key being examined.

	If, however the key is present in its local store, it will compare VCLK to VCcc (again, VCcc in this case is simply the vector clock associated with the key from the current gossip update that is being examined).  

If VCLK > VCcc, the key and its accompanying data remain unchanged in the local store.  

If VCLK < VCcc, the local replica will store the incoming key-value pair, timestamp, and VCcc in the local store in the following form:

{“key”:{“value”:<value>, “vc”:<VCcc>, “ts”<timestamp>}}

If VCLK || VCcc (|| = “concurrent with”) then the value with the greater timestamp will be the value that is kept.  Also, VCLK = pairwise\_max(VCcc, VCLK).  Then the key-value pair with the greater timestamp, the new VCLK, and the greater timestamp itself will be stored in the local store in the following form:

{“key”:{“value”:<value>, “vc”:<VCLK>, “ts”:<timestamp>}}

