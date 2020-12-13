from client import Client
print_response = True

import unittest
import requests
import time
import os


addResponse_Success = { 	"message":		"Added successfully",
                           "replaced": 	False,
                           "status_code":	201}
addResponseError_NoValue = {"error":	"Value is missing",
                            "message":	"Error in PUT",
                            "status_code":	400}
addResponseError_NoKey = {	"error":	"Value is missing",
                              "message":	"Error in PUT",
                              "status_code":	400}
addResponseError_longKey = {"error":	"Key is too long",
                            "message":	"Error in PUT",
                            "status_code":	400}

updateResponse_Success = {"message":		"Updated successfully",
                          "replaced":		True,
                          "status_code":	200}
updateResponseError_NoKey = addResponseError_NoKey
updateResponseError_NoValue = addResponseError_NoValue

getResponse_Success = {	"doesExist":	True,
                           "message":		"Retrieved successfully",
                           "value":		"Default Value, should be changed based on input",
                           "status_code":	200}
getResponse_NoKey = {	"doesExist":	False,
                         "error":		"Key does not exist",
                         "message":		"Error in GET",
                         "status_code":	404}

delResponse_Success = {	"doesExist":	True,
                           "message":		"Deleted successfully",
                           "status_code":	200}
delResponse_NoKey = {	"doesExist":	False,
                         "error":		"Key does not exist",
                         "message":		"Error in DELETE",
                         "status_code":	404}

getKeyCountResponse_Success = {
    "message":		"Key count retrieved successfully",
    "status_code":	200}

############################### Docker Linux Commands ###########################################################
def removeSubnet(subnetName):
    command = "docker network rm " + subnetName
    os.system(command)
    time.sleep(2)

def createSubnet(subnetAddress, subnetName):
    command  = "docker network create --subnet=" + subnetAddress + " " + subnetName
    os.system(command)
    time.sleep(2)

def buildDockerImage():
    command = "docker build -t kvs:4.0 ."
    os.system(command)

def stopAndRemoveAll():
    nodeCount = 4
    for i in range(1,nodeCount+1):
        os.system("docker stop node%d"%i)

    time.sleep(1)

    for i in range(1,nodeCount+1):
        os.system("docker rm node%d"%i)

    time.sleep(1)

def runInstances(ins):
    for in_ in ins:
        cmd = "docker run -d -p %d:13800 " \
              "--net=%s " \
              "--ip=%s " \
              "--name=%s " \
              "-e ADDRESS=%s:13800 " \
              "-e VIEW=\"%s\" " \
              "-e REPL_FACTOR=%d " \
              "kvs:4.0" % \
              (in_["host_port"],in_["subnet"],in_["ip_address"],in_["name"],in_["ip_address"],in_["view"],in_["repl_factor"])

        os.system(cmd)

    time.sleep(5)

    return

def stopAndRemoveInstance(instanceName):
    stopCommand = "docker stop " + instanceName
    removeCommand = "docker rm " + instanceName
    os.system(stopCommand)
    time.sleep(2)
    os.system(removeCommand)

def connectToNetwork(subnetName, instanceName):
    command = "docker network connect " + subnetName + " " + instanceName
    os.system(command)

def disconnectFromNetwork(subnetName, instanceName):
    command = "docker network disconnect " + subnetName + " " + instanceName
    os.system(command)

################################# Unit Test Class ############################################################

extra_credit = False # this feature is WIP
print_response = True

class TestHW3(unittest.TestCase):
    # buildDockerImage()
    # createSubnet("10.10.0.0/16","kv_subnet")
    # createSubnet("10.11.0.0/16","kv_subnet_partition")

    def key_count_helper(self,response):
        self.assertEqual(response["status_code"],200)
        self.assertEqual(response["message"],"Key count retrieved successfully")

        return response["key-count"],response["shard-id"]

    def get_shards_helper(self,response,shard_count):
        self.assertEqual(response["status_code"],200)
        self.assertEqual(response["message"],"Shard membership retrieved successfully")
        self.assertEqual(len(response["shards"]),shard_count)

        return response["shards"]

    def get_shard_helper(self,response,id):
        self.assertEqual(response["status_code"],200)
        # self.assertEqual(response["message"],"Shard information retrieved successfully")
        self.assertEqual(response["shard-id"],id)

        return response["key-count"],response["replicas"]

    def assertEqual_helper(self, a, b):
        a = a.copy()
        a.pop("address",None)
        self.assertEqual(a,b)

    def add_nodes(self,shards,replicas,shard_id):
        for node in replicas:
            self.assertTrue(node not in shards["nodes"])
            shards["nodes"].append(node)

        shards["shards"][shard_id] = replicas

    def nodes_equal(self,a,b):
        self.assertEqual(len(a),len(b))
        for node in a:
            self.assertTrue(node in b)

    def check_shard_id_by_address(self,response,shards,address):
        shard_id = self.get_shard_id_by_address(shards,address)
        if "address" in response:
            address_ = response["address"]
            self.assertNotEqual(address_,address)
            shard_id_ = self.get_shard_id_by_address(shards,address_)
            self.assertNotEqual(shard_id_,shard_id)

            return shard_id_

        return shard_id

    def get_shard_id_by_address(self,shards,address):
        for shard_id in shards["shards"]:
            replicas = shards["shards"][shard_id]
            if address in replicas:
                return shard_id

    def key_count_add(self,key_count,shard_id):
        if shard_id in key_count:
            key_count[shard_id] += 1
        else:
            key_count[shard_id] = 1

    def get_causal_context(self, response, pos):
        if response.get('causal-context', {}) == {}:
            print(f"\n\nCAUSAL CONTEXT IS EMPTY AT {pos}")
        else:
            print(f"\n\nNOT EMPTY AT {pos}")
        return response.get('causal-context', {})
                
    def test_network_partition_3(self):
            # test causal consistency
            alice = Client(print_response=print_response)
            bob = Client(print_response=print_response)
            carol = Client(print_response=print_response)

            shard_count,repl_factor,nodes = 1,2,["10.10.0.2:13800","10.11.0.2:13800"]
            view = ",".join(nodes)
            ins = [
                {"subnet":"kv_subnet","host_port":13800,"ip_address":"10.10.0.2","address":"10.10.0.2:13800","name":"node1","view":view,"repl_factor":repl_factor},
                {"subnet":"kv_subnet_partition","host_port":13801,"ip_address":"10.11.0.2","address":"10.11.0.2:13800","name":"node2","view":view,"repl_factor":repl_factor},
            ]

            # stopAndRemoveAll()
            # runInstances(ins)

            address1,port1 = ins[0]["address"],ins[0]["host_port"]
            address2,port2 = ins[1]["address"],ins[1]["host_port"]

            # # by default, there is a network partition between kv_subnet and kv_subnet_partition, heal it before testing
            # # node2 -> node1 through bridge (subnet) kv_subnet
            # # node1 -> node2 through bridge (subnet) kv_subnet_partition
            connectToNetwork("kv_subnet","node2")
            connectToNetwork("kv_subnet_partition","node1")

            # initialize variables a and b
            client = Client(causal_context_flag=True,print_response=print_response)
            response = client.putKey("a","init a",port1)
            #self.get_causal_context(response, 'put a')
            response = client.putKey("b","init b",port2)
            #self.get_causal_context(response, 'put b')
            time.sleep(5)
            response = client.getKey("a",port2)
            self.assertEqual(response["value"],"init a")
            #self.get_causal_context(response, 'get a')
            response = client.getKey("b",port1)
            #self.get_causal_context(response, 'get b')
            self.assertEqual(response["value"],"init b")

            # create network partition
            disconnectFromNetwork("kv_subnet","node2")
            disconnectFromNetwork("kv_subnet_partition","node1")

            # Alice writes a="Bob smells" to node1
            a = "Bob smells"
            response = alice.putKey("a",a,port1)
            #self.get_causal_context(response, 'ALICE PUT a bobsmells')
            self.assertEqual_helper(response,updateResponse_Success)

            # Bob reads a from node1 and writes b="Fuck you Alice" to node2
            response = bob.getKey("a",port1)
            #self.get_causal_context(response, 'BOB GET a bobsmells')
            self.assertEqual(response["value"],a)

            b = "Fuck you Alice"
            response = bob.putKey("b",b,port1)
            #self.get_causal_context(response, 'BOB PUT a fualice')
            self.assertEqual_helper(response,updateResponse_Success)

             # Alice writes a="Bob smells" to node1
            a = "Fuck you Bob you dumb, stupid piece of garbage"
            response = alice.putKey("a",a,port1)
            #self.get_causal_context(response, 'ALICE PUT a bobsmells')
            self.assertEqual_helper(response,updateResponse_Success)


            
            # Carol reads b from node2
            response = carol.getKey("b",port1)
            #self.get_causal_context(response, 'CAROLD GET b')
            self.assertEqual(response["value"],b)

            # Carol reads a from node2 and gets NACK or "Bob smells"
            # BREAKING CAUSAL CONSISTENCY HERE BECAUSE CAROL READ AN EFFECT WITHOUT A CAUSE
            response = carol.getKey("a",port2)
            #self.get_causal_context(response, 'CAROL GET a')
            self.assertTrue(response["status_code"] in [200,400])
            if response["status_code"] == 400: # nack
                self.assertEqual(response["error"],"Unable to satisfy request")
                self.assertEqual(response["message"],"Error in GET")
            elif response["status_code"] == 200:
                self.assertEqual(response["value"],a)

            # Alice writes a="Bob still smells" to node2
            a = "Bob still smells"
            response = alice.putKey("a",a,port2)
            self.assertEqual_helper(response,updateResponse_Success)

            # Carol reads a from node2 and gets "Bob still smells"
            response = carol.getKey("a",port2)
            self.assertEqual(response["value"],a)

    # def test_network_partition_2(self):
    #         # test causal consistency
    #         alice = Client(print_response=print_response)
    #         bob = Client(print_response=print_response)
    #         carol = Client(print_response=print_response)

    #         shard_count,repl_factor,nodes = 1,2,["10.10.0.2:13800","10.11.0.2:13800"]
    #         view = ",".join(nodes)
    #         ins = [
    #             {"subnet":"kv_subnet","host_port":13800,"ip_address":"10.10.0.2","address":"10.10.0.2:13800","name":"node1","view":view,"repl_factor":repl_factor},
    #             {"subnet":"kv_subnet_partition","host_port":13801,"ip_address":"10.11.0.2","address":"10.11.0.2:13800","name":"node2","view":view,"repl_factor":repl_factor},
    #         ]

    #         # stopAndRemoveAll()
    #         # runInstances(ins)

    #         address1,port1 = ins[0]["address"],ins[0]["host_port"]
    #         address2,port2 = ins[1]["address"],ins[1]["host_port"]

    #         # # by default, there is a network partition between kv_subnet and kv_subnet_partition, heal it before testing
    #         # # node2 -> node1 through bridge (subnet) kv_subnet
    #         # # node1 -> node2 through bridge (subnet) kv_subnet_partition
    #         connectToNetwork("kv_subnet","node2")
    #         connectToNetwork("kv_subnet_partition","node1")

    #         # initialize variables a and b
    #         client = Client(causal_context_flag=True,print_response=print_response)
    #         response = client.putKey("a","init a",port1)
    #         #self.get_causal_context(response, 'put a')
    #         response = client.putKey("b","init b",port2)
    #         #self.get_causal_context(response, 'put b')
    #         time.sleep(5)
    #         response = client.getKey("a",port2)
    #         self.assertEqual(response["value"],"init a")
    #         #self.get_causal_context(response, 'get a')
    #         response = client.getKey("b",port1)
    #         #self.get_causal_context(response, 'get b')
    #         self.assertEqual(response["value"],"init b")

    #         # create network partition
    #         disconnectFromNetwork("kv_subnet","node2")
    #         disconnectFromNetwork("kv_subnet_partition","node1")

    #         # Alice writes a="Bob smells" to node1
    #         a = "Bob smells"
    #         response = alice.putKey("a",a,port1)
    #         #self.get_causal_context(response, 'ALICE PUT a bobsmells')
    #         self.assertEqual_helper(response,updateResponse_Success)

    #         # Bob reads a from node1 and writes b="Fuck you Alice" to node2
    #         b = "Fuck you Alice"
    #         response = bob.getKey("a",port1)
    #         #self.get_causal_context(response, 'BOB GET a bobsmells')
    #         self.assertEqual(response["value"],a)

    #         response = bob.putKey("b",b,port2)
    #         #self.get_causal_context(response, 'BOB PUT a fualice')
    #         self.assertEqual_helper(response,updateResponse_Success)
            
    #         # Carol reads b from node2
    #         response = carol.getKey("b",port2)
    #         #self.get_causal_context(response, 'CAROLD GET b')
    #         self.assertEqual(response["value"],b)
    #         print(f'CAROL CONTEXT:{carol.causal_context}')

    #         # Carol reads a from node2 and gets NACK or "Bob smells"
    #         # BREAKING CAUSAL CONSISTENCY HERE BECAUSE CAROL READ AN EFFECT WITHOUT A CAUSE
    #         response = carol.getKey("a",port2)
    #         #self.get_causal_context(response, 'CAROL GET a')
    #         self.assertTrue(response["status_code"] in [200,400])
    #         if response["status_code"] == 400: # nack
    #             self.assertEqual(response["error"],"Unable to satisfy request")
    #             self.assertEqual(response["message"],"Error in GET")
    #         elif response["status_code"] == 200:
    #             self.assertEqual(response["value"],a)

    #         # Alice writes a="Bob still smells" to node2
    #         a = "Bob still smells"
    #         response = alice.putKey("a",a,port2)
    #         self.assertEqual_helper(response,updateResponse_Success)

    #         # Carol reads a from node2 and gets "Bob still smells"
    #         response = carol.getKey("a",port2)
    #         self.assertEqual(response["value"],a)

if __name__ == '__main__':
	unittest.main()