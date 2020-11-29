 establish some shorthand:

VCcc = vector clock from request&#39;s causal context.

VCL = vector clock local, or local vector clock (vector clock for the local replica itself)

VCLK = vector clock in the local store that is attached to the same key as VCcc (the key from the client request&#39;s causal context, or from the miss dictionary that is associated with a gossip update being received by a replica from another replica in the shard).

VCWK = vector clock in the local store associated with the key that the client (or other replica if the request is a forwarded request) is trying to access.

VCRK = vector clock in the local store associated with the key that the client is trying to read

**For PUT requests:**

If the key that the client is attempting to write to _is not_ present in the local store and the client request&#39;s causal context is empty, increment local position in VCL. Create timestamp. Store the key-value pair from the client request, VCL, and timestamp in the following form:

{&quot;key&quot;:{&quot;value&quot;:\&lt;value\&gt;, &quot;vc&quot;:\&lt;VCL\&gt;, &quot;ts&quot;:\&lt;timestamp\&gt;}}

Return this very same dictionary above for the client to maintain as causal context.

If the key that the client is attempting to write to _is_ present in the local store, and the client request&#39;s causal context is empty, increment local position in VCL. Then VCWK = pairwise\_max(VCL, VCWK). Create timestamp. Store the key-value pair from the client request, new VCWK, and timestamp in the store in the following form:

{&quot;key&quot;:{&quot;value&quot;:\&lt;value\&gt;, &quot;vc&quot;:\&lt;VCWK\&gt;, &quot;ts&quot;:\&lt;timestamp\&gt;}}

Return this very same dictionary above for the client to maintain as causal context.

If the key that the client is attempting to write to _is not_ present in the local store and the client request&#39;s causal context is not empty, increment local position in VCL. Then VCWK = pairwise\_max(VCL, VCcc). Create timestamp. Store key-value pair from client request, VCWK, and timestamp in the local store in the following form:

{&quot;key&quot;:{&quot;value&quot;:\&lt;value\&gt;, &quot;vc&quot;:\&lt;VCWK\&gt;, &quot;ts&quot;:\&lt;timestamp\&gt;}}

Return this very same dictionary above for the client to maintain as causal context

If the key that the client is attempting to write to _is_ present in the store and the client request&#39;s causal context is not empty, increment the local position in the VCL. Then VCWK = pairwise\_max(VCcc, VCWK). Create timestamp. Store the key-value pair from the client request, the timestamp, and new VCWK in the local store in the following form:

{&quot;key&quot;:{&quot;value&quot;:\&lt;value\&gt;, &quot;vc&quot;:\&lt;VCWK\&gt;, &quot;ts&quot;:\&lt;timestamp\&gt;}}

Return the very same dictionary above for the client to maintain as causal context.

**Forwarding:**

Obviously, any time a request is stored in the local store, that request data must be forwarded to the other replicas in the shard. If, when attempting to forward a write to the other replicas in the shard, it is discovered that another replica is down (unresponsive), that write will be buffered in a local &quot;miss dictionary&quot; in the following form:

{\&lt;address\_of\_down\_replica\&gt;: [{&quot;key&quot;:{&quot;value&quot;\&lt;value\&gt;, &quot;vc&quot;:\&lt;VCWK\&gt;, &quot;ts&quot;:\&lt;timestamp\&gt;,}}]}

This &quot;miss dictionary&quot; will be of the overall following form:

{{\&lt;address\_of\_down\_replica\_1\&gt;:&quot;VCL&quot;:\&lt;VCL\&gt;, &quot;miss\_list&quot;:[{&quot;missed\_key\_1&quot;:{&quot;value&quot;:\&lt;value\&gt;, &quot;vc&quot;:\&lt;VCWK1\&gt;,&quot;ts&quot;:\&lt;timestamp1\&gt;}}, {missed\_key\_2&quot;:{&quot;value&quot;:\&lt;value\&gt;, &quot;vc&quot;:\&lt;VCWK2\&gt;, &quot;ts&quot;:\&lt;timestamp2\&gt;}}, …, {&quot;missed\_key\_n&quot;:{&quot;value&quot;:\&lt;value\&gt;, &quot;vc&quot;:\&lt;VCWKn\&gt;, &quot;ts&quot;:\&lt;timestamp\_n\&gt;}}]}, {\&lt;address\_of\_down\_replica\_2\&gt;:&quot;VCL&quot;:\&lt;VCL\&gt;, &quot;miss\_list&quot;:[{&quot;missed\_key\_1&quot;:{&quot;value&quot;:\&lt;value\&gt;, &quot;vc&quot;:\&lt;VCWK1\&gt;,&quot;ts&quot;:\&lt;timestamp1\&gt;}}, {missed\_key\_2&quot;:{&quot;value&quot;:\&lt;value\&gt;, &quot;vc&quot;:\&lt;VCWK2\&gt;, &quot;ts&quot;:\&lt;timestamp2\&gt;}}, …, {missed\_key\_n&quot;:{&quot;value&quot;:\&lt;value\&gt;, &quot;vc&quot;:\&lt;VCWKn\&gt;, &quot;ts&quot;:\&lt;timestamp\_n\&gt;}}]}, …, {\&lt;address\_of\_down\_replica\_n\&gt;:&quot;VCL&quot;:\&lt;VCL\&gt;, &quot;miss\_list&quot;: [{&quot;missed\_key\_1&quot;:{&quot;value&quot;:\&lt;value\&gt;, &quot;vc&quot;:\&lt;VCWK1\&gt;,&quot;ts&quot;:\&lt;timestamp1\&gt;}}, {missed\_key\_2&quot;:{&quot;value&quot;:\&lt;value\&gt;, &quot;vc&quot;:\&lt;VCWK2\&gt;, &quot;ts&quot;:\&lt;timestamp2\&gt;}}, …, {missed\_key\_n&quot;:{&quot;value&quot;:\&lt;value\&gt;, &quot;vc&quot;:\&lt;VCWKn\&gt;, &quot;ts&quot;:\&lt;timestamp\_n\&gt;}}]}}

As you can see, this is a dictionary in which each member is a list of dictionaries. Parent\_Dictionary(address\_of\_down\_replica\_dictionary(list(individual\_dictionaries\_for\_each\_miss)))

Also note that the &quot;VCL&quot; for each &quot;address\_of\_down\_replica&quot; is not to be inserted until the time that the &quot;miss list&quot; is actually sent (so as to insure that the receiving replica gets the most recent form of the VCL, of course).

**For GET requests** :

If the key _is_ present in the local store, and the client request&#39;s causal context is empty, increment the local position in the VCL. Return the key-value pair that the client is requesting along with the VCRK and the timestamp associated with the requested key in the local store in the following form:

{&quot;key&quot;:{&quot;value&quot;:\&lt;value\&gt;, &quot;vc&quot;:\&lt;VCRK\&gt;, &quot;ts&quot;:\&lt;timestamp\&gt;}}

If the key _is not_ present in the local store and the client request&#39;s causal context is empty, return the following:

{&quot;error&quot;: &quot;Unable to satisfy request&quot;, &quot;message&quot;: &quot;Error in GET&quot;}, 400

If the key _is not_ present in the local store, and the client request&#39;s causal context is not empty, check to see if the key that the client has in its causal context is the same as the key it is requesting access to. If they are one and same key, simply return the client&#39;s causal context back to it in the following form:

{&quot;key&quot;:{&quot;value&quot;\&lt;value\&gt;, &quot;vc&quot;:\&lt;VCcc\&gt;, &quot;ts&quot;:\&lt;timestamp\&gt;}}

However, if they are not one and the same key, return the following:

{&quot;error&quot;: &quot;Unable to satisfy request&quot;, &quot;message&quot;: &quot;Error in GET&quot;}, 400

If the key _is_ present in the local store and the client request&#39;s causal context is not empty, compare VCcc to VCRK. If VCcc \&gt; VCRK (client is in the future relative to requested key and shouldn&#39;t be able to read the past) then return the following:

{&quot;error&quot;: &quot;Unable to satisfy request&quot;, &quot;message&quot;: &quot;Error in GET&quot;}, 500

However, if VCcc \&lt;= VCRK (client is in the past relative to requested key, it&#39;s fine to let them read the future) return the requested key-value pair, timestamp associated with the requested key in the local store, and the VCcc in the following form:

{&quot;key&quot;:{&quot;value&quot;:\&lt;value\&gt;, &quot;vs&quot;:\&lt;VCcc\&gt;, &quot;ts&quot;:\&lt;timestamp\&gt;}}

**Gossip:**

_Sending the gossip_

Each replica will iteratively go through their &quot;miss dictionary&quot; and send the respective &quot;miss list&quot; to the appropriate address. A function that performs this action will run every &quot;x&quot; milliseconds or half second, or whatever time interval seems most appropriate.

Upon discovering that a replica previously thought to be down is now back up and has received the gossip update successfully, the address associated with that replica in the &quot;miss dictionary&quot; will be wiped clean (until it is discovered that replica has gone down again – at that point the miss list for that replica will begin to build again in the local &quot;miss dictionary&quot;).

This &quot;gossip&quot; will be sent to a different endpoint; not the endpoint associated with the standard &quot;PUT&quot; operations.

_Receiving the gossip:_

Upon receiving a gossip update from another replica in the shard, the local replica will iterate through the &quot;miss queue&quot; and for each key it examines, it will first set the VCL = pairwise\_max(VCL, VCL\_from\_gossip).

If the key is not present in the local store, it will simply store the miss in the local store in its received form, i.e.;

{&quot;key&quot;:{&quot;value&quot;:\&lt;value\&gt;, &quot;vc&quot;:\&lt;VCcc\&gt;, &quot;ts&quot;:\&lt;timestamp\&gt;}}

where, in this case, VCcc is simply the vector clock associated with the particular key being examined.

If, however the key _is_ present in its local store, it will compare VCLK to VCcc (again, VCcc in this case is simply the vector clock associated with the key from the current gossip update that is being examined).

If VCLK \&gt; VCcc, the key and its accompanying data remain unchanged in the local store.

If VCLK \&lt; VCcc, the local replica will store the incoming key-value pair, timestamp, and VCcc in the local store in the following form:

{&quot;key&quot;:{&quot;value&quot;:\&lt;value\&gt;, &quot;vc&quot;:\&lt;VCcc\&gt;, &quot;ts&quot;\&lt;timestamp\&gt;}}

If VCLK || VCcc (|| = &quot;concurrent with&quot;) then the value with the greater timestamp will be the value that is kept. Also, VCLK = pairwise\_max(VCcc, VCLK). Then the key-value pair with the greater timestamp, the new VCLK, and the greater timestamp itself will be stored in the local store in the following form:

{&quot;key&quot;:{&quot;value&quot;:\&lt;value\&gt;, &quot;vc&quot;:\&lt;VCLK\&gt;, &quot;ts&quot;:\&lt;timestamp\&gt;}}

