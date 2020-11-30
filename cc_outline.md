
First, let’s establish some shorthand:

VCK = vector clock associated with key
VCcc = vector clock from client request causal context

For both PUT and GET, there are four parent cases…

4 parent cases:
		
1). Key is present in store, client request causal context empty
		
2). Key is not present in store, client request causal context empty

3). Key is present in store, client request causal context not empty

4). Key is not present in store, client request causal context not empty
 

For PUT requests:
	
For case 1 (Key is present in store, client request causal context empty):

Increment local position in VCK. Store the key-value pair, the VCK and the index of the local replica in the view list in the local store in the following form:

{“key”:{“value”:<value>, “vc”:<VCK>, “node_id”:<index>}}
	
	Then return the following dictionary for the client to maintain as causal context:
	
		{“cm”:{“key”:{“value”:<value>, “vc”:<VCK>, “node_id”:<index>}}
	
	For case 2 (Key is not present in store, client request causal context empty):
 
Create VCK.  Increment local position in VCK to 1.  Store the key-value pair, the VCK and the index of the local replica in the view list in the local store in the following form:

{“key”:{“value”:<value>, “vc”:<VCK>, “node_id”:<index>}}
	
	For case 3: (Key is present in store, client request causal context not empty):

If client request causal context has an entry for the key being written to:

Increment local position in VCK.
VCK = pairwise_max(VCK, VCcc)
Store the key-value pair, index of the local replica in the view list, and the VCK in the local store in the following form:

{“key”:{“value”:<value>, “vc”:<VCK>, “node_id”:<index>}}

Return the following dictionary for the client to maintain as causal context:

{“causal-context”:{“key”:{“value”:<value>, “vc”:<VCK>, “node_id”:<index_id>}, “key_1”:{“value”:<value_1>, “vc”:<VCK_1>, “node_id”:<index_id_1>}, … , “key_n”:{“value”:<value_n>, “vc”:<VCK_n>, “node_id”:<index_id_n>}}

The idea here is that we are not getting rid of any of the client’s causal context.  Whatever the client gave the local replica as causal context we are giving back PLUS the updated version of the key that the client just wrote to.

If client request causal context does not have an entry for the key being written to:

Increment local position in VCK.  
Store the key-value pair, the VCK and the index of the local replica in the view list in the local store in the following form:

{“key”:{“value”:<value>, “vc”:<VCK>, “node_id”:<index>}}
	
Return the following dictionary for the client to maintain as causal context:

{“causal-context”:{“key”:{“value”:<value>, “vc”:<VCK>, “node_id”:<index_id>}, “key_1”:{“value”:<value_1>, “vc”:<VCK_1>, “node_id”:<index_id_1>}, … , “key_n”:{“value”:<value_n>, “vc”:<VCK_n>, “node_id”:<index_id_n>}}

Again, the idea here is that we are not getting rid of any of the client’s causal context.  Whatever the client gave the local replica as causal context we are giving back PLUS the updated version of the key that the client just wrote to.

	For case 4:

		If client request causal context has an entry for the key being written to:
			
Extract VCcc from causal context.  
Increment local position in VCcc.  
Store key-value pair, the VCcc and the index of the local replica in the view list in the local store in the following form:

{“key”:{“value”:<value>, “vc”:<VCK>, “node_id”:<index>}}

Return the following dictionary for the client to maintain as causal context:

{“causal-context”:{“key”:{“value”:<value>, “vc”:<VCK>, “node_id”:<index_id>}, “key_1”:{“value”:<value_1>, “vc”:<VCK_1>, “node_id”:<index_id_1>}, … , “key_n”:{“value”:<value_n>, “vc”:<VCK_n>, “node_id”:<index_id_n>}}

Again, the idea here is that we are not getting rid of any of the client’s causal context.  Whatever the client gave the local replica as causal context we are giving back PLUS the updated version of the key that the client just wrote to.

If client request causal context does not have an entry for the key being written to:

Create VCK.  
Increment local position in VCK to 1.  
Store the key-value pair, the VCK and the index of the local replica in the view list in the local store in the following form:

{“key”:{“value”:<value>, “vc”:<VCK>, “node_id”:<index>}}
	
Return the following dictionary for the client to maintain as causal context:

{“causal-context”:{“key”:{“value”:<value>, “vc”:<VCK>, “node_id”:<index_id>}, “key_1”:{“value”:<value_1>, “vc”:<VCK_1>, “node_id”:<index_id_1>}, … , “key_n”:{“value”:<value_n>, “vc”:<VCK_n>, “node_id”:<index_id_n>}}

Again, the idea here is that we are not getting rid of any of the client’s causal context.  Whatever the client gave the local replica as causal context we are giving back PLUS the updated version of the key that the client just wrote to.

	
Forwarding:

	Obviously, any time a request is stored in the local store, that request data must be forwarded to the other replicas in the shard.  If, when attempting to forward a write to the other replicas in the shard, it is discovered that another replica is down (unresponsive), that write will be buffered in a local "miss dictionary" in the following form:

{<address_of_down_replica>: [{“key”:{"value"<value>, "vc":<VCK>, “node_id":<index_id>,}}]}

	This “miss dictionary" will be of the overall following form:

{{<address_of_down_replica_1>: “miss_list”:[{"missed_key_1":{"value":<value>, "vc":<VCK1>,”node_id”:<index_id_1>}}, {missed_key_2":{"value":<value>, "vc":<VCK2>, "node_id”:<index_id_2>}}, …, {“missed_key_n":{"value”:<value>, “vc”:<VCKn>, “ts”:<index_id_n>}}]}, {<address_of_down_replica_2>: “miss_list”:[{"missed_key_1":{"value":<value>, "vc":<VCK1>,”node_id”:<index_id_1>}}, {missed_key_2":{"value":<value>, "vc":<VCK2>, "node_id”:<index_id2>}}, …, {missed_key_n":{"value”:<value>, “vc”:<VCKn>, “node_id”:<index_id_n>}}]}, …, {<address_of_down_replica_n>:”VCL”: “miss_list”: [{"missed_key_1":{"value":<value>, "vc":<VCK1>,”node_id”:<index_id_1>}}, {missed_key_2":{"value":<value>, "vc":<VCK2>, "node_id”:<index_id_2>}}, …, {missed_key_n":{"value”:<value>, “vc”:<VCKn>, “node_id”:<index_id_n>}}]}}

As you can see, this is a dictionary in which each member is a list of dictionaries.  Parent_Dictionary(address_of_down_replica_dictionary(list(individual_dictionaries_for_each_miss)))



For GET requests:

For case 1 (Key is present in store, client request causal context empty):

		Increment local position in VCK.

Simply return the requested data to the client in the following form:

		{
           		"message"       : "Retrieved successfully",
           		"doesExist"     : true,
          		"value"         : "sampleValue",
           		"address"       : "10.10.0.4:13800",
"causal-context": {“key”:{“value”:<value>,                                                                    “vc”:<VCK>, “node_id”:<index_id>}}},
       		}
       		200

	For case 2 (Key is not present in store, client request causal context empty):

		NACK the client.  Return the following:

	{
           "message"       : "Error in GET",
           "error"         : "Key does not exist",
           "doesExist"     : false,
           "address"       : "10.10.0.4:13800",
           "causal-context": {},
         }
       	 404


	For case 3: (Key is present in store, client request causal context not empty):

		If client request causal context has entry for key being read:

Compare VCK to VCcc. 
 
If VCcc > VCK: 
Return the client’s own version of the key back to it.
(along with all of its causal context)
If VCcc <= VCK:
	Increment local position in VCK.
Return the client’s requested data. (along with all of its causal context)
If VCcc || VCK:
Split brain. We shouldn’t return the client’s data to it until the partition or whatever is causing the split brain is healed and the split brain is repaired by gossip.  Therefore, NACK the client.
		
If client request causal context does not have entry for key being read: 

	Increment local position in VCK.
Return the requested data to client (along with all of its causal context which should now also include the key being read).
	
For case 4: (Key is not present in store, client request causal context not empty):

If client causal context has entry for key being requested:
Return key data from client’s own causal context back to it (along with all of its causal context)
		
		If client causal context does not have entry for key being requested:
	


	NACK the client. 404.
                
Gossip:

	Sending the gossip
	
	Each replica will iteratively go through their “miss dictionary” and send the respective “miss list” to the appropriate address.  A function that performs this action will run every “x” milliseconds or half second, or whatever time interval seems most appropriate.  

Upon discovering that a replica previously thought to be down is now back up and has received the gossip update successfully, the address associated with that replica in the “miss dictionary” will be wiped clean (until it is discovered that replica has gone down again – at that point the miss list for that replica will begin to build again in the local “miss dictionary”).

This “gossip” will be sent to a different endpoint; not the endpoint associated with the standard “PUT” operations.

Receiving the gossip:

	Upon receiving a gossip update from another replica in the shard, the local replica will iterate through the “miss queue" and examine each key and its data.
  
	If the key is not present in the local store, it will simply store the miss in the local store in its received form, i.e.;

	{“key”:{“value”:<value>,  “vc”:<VCcc>, “node_id”:<index_id>}}

where, in this case, VCcc is simply the vector clock associated with the particular key being examined.

	If, however the key is present in its local store, it will compare VCK to VCcc (again, VCcc in this case is simply the vector clock associated with the key from the current gossip update that is being examined).  

If VCK > VCcc, the key and its accompanying data remain unchanged in the local store.  

If VCK < VCcc, the local replica will store the incoming key-value pair, timestamp, and VCcc in the local store in the following form:

{“key”:{“value”:<value>, “vc”:<VCcc>, “ts”<timestamp>}}

If VCK || VCcc (|| = “concurrent with”) then the value with the greater node_id will be the value that is kept.  Also, VCK = pairwise_max(VCcc, VCK).  Then the key-value pair with the greater node_id, the new VCK, and the greater node_id itself will be stored in the local store in the following form:

{“key”:{“value”:<value>, “vc”:<VCK>, “node_id”:<index_id>}}
