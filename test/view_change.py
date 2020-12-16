###################
# Course: CSE 138
# Date: Fall 2020
# Assignment: #4
# Author: Reza NasiriGerdeh, Aleck Zhang
# Email: rnasirig@ucsc.edu, jzhan293@ucsc.edu
###################

import unittest
import requests
import time
import os
from client import Client

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

extra_credit = True # this feature is WIP
print_response = True

class TestHW3(unittest.TestCase):
    buildDockerImage()
    createSubnet("10.10.0.0/16","kv_subnet")
    createSubnet("10.11.0.0/16","kv_subnet_partition")

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


    def view_change_helper(self,old_shard_count,old_nodes,old_ins,new_shard_count,new_repl_factor,new_nodes,new_view,new_ins):
        client = Client(causal_context_flag=False,print_response=print_response)

        old_node_count,new_node_count = len(old_nodes),len(new_nodes)

        # stopAndRemoveAll()
        # runInstances(old_ins)
        # runInstances(new_ins) # todo

        port = old_ins[0]["host_port"]
        response = client.getShards(port)
        shard_ids = self.get_shards_helper(response,old_shard_count)

        shards = {"nodes":[],"shards": {}}
        for shard_id in shard_ids:
            response = client.getShard(port,shard_id)
            _, replicas = self.get_shard_helper(response,shard_id)
            self.add_nodes(shards,replicas,shard_id)

        self.nodes_equal(old_nodes,shards["nodes"])

        keys = 100
        key_counts0 = {}

        for i in range(keys):
            key = "test_view_change_%d"%i
            value = "I don't care %d"%i
            update_value = "I do care %d"%i
            address,port = old_ins[i%old_node_count]["address"],old_ins[i%old_node_count]["host_port"]

            response = client.putKey(key,value,port)
            self.assertEqual_helper(response,addResponse_Success)

            shard_id = self.check_shard_id_by_address(response,shards,address)
            self.key_count_add(key_counts0,shard_id)

            # get
            response = client.getKey(key,port)
            expected = getResponse_Success.copy()
            expected["value"] = value
            self.assertEqual_helper(response,expected)
            self.assertEqual(shard_id,self.check_shard_id_by_address(response,shards,address))

            # update
            response = client.putKey(key,update_value,port)
            self.assertEqual_helper(response,updateResponse_Success)

        print(key_counts0)
        time.sleep(5)
        for in_ in old_ins:
            response = client.keyCount(in_["host_port"])
            key_count, shard_id = self.key_count_helper(response)
            self.assertEqual(key_count,key_counts0[shard_id])

        port = old_ins[0]["host_port"]
        response = client.viewChange(new_view,new_repl_factor,port)
        key_counts1 = self.view_change_response_helper(response,new_nodes,new_shard_count)
        print(key_counts1)

        time.sleep(5)
        port = new_ins[0]["host_port"]
        response = client.getShards(port)
        shard_ids = self.get_shards_helper(response,new_shard_count)
        shards = {"nodes":[],"shards": {}}
        for shard_id in shard_ids:
            response = client.getShard(port,shard_id)
            _, replicas = self.get_shard_helper(response,shard_id)
            self.add_nodes(shards,replicas,shard_id)

        self.nodes_equal(new_nodes,shards["nodes"])

        for in_ in new_ins:
            response = client.keyCount(in_["host_port"])
            key_count, shard_id = self.key_count_helper(response)
            self.assertEqual(key_count,key_counts1[shard_id])

        for i in range(keys):
            key = "test_view_change_%d"%i
            value = "I do care %d"%i
            address,port = new_ins[i%new_node_count]["address"],new_ins[i%new_node_count]["host_port"]
            # get
            response = client.getKey(key,port)
            expected = getResponse_Success.copy()
            expected["value"] = value
            self.assertEqual_helper(response,expected)
            self.check_shard_id_by_address(response,shards,address)

    def view_change_response_helper(self,response,nodes,shard_count):
        self.assertEqual(response["message"],"View change successful")
        self.assertEqual(len(response["shards"]),shard_count)
        keycounts = {}
        nodes_ = []
        for shard in response["shards"]:
            keycounts[shard["shard-id"]] = shard["key-count"]
            nodes_.extend(shard["replicas"])

        self.nodes_equal(nodes_,nodes)

        return keycounts

    # def test_view_change_1(self):
    #     old_shard_count,old_repl_factor,old_nodes = 1,1,["10.10.0.2:13800"]
    #     old_view = ",".join(old_nodes)

    #     old_ins = [
    #         {"subnet":"kv_subnet","host_port":13800,"ip_address":"10.10.0.2","address":"10.10.0.2:13800","name":"node1","view":old_view,"repl_factor":old_repl_factor},
    #     ]
    #     new_ins = [
    #         {"subnet":"kv_subnet","host_port":13800,"ip_address":"10.10.0.2","address":"10.10.0.2:13800","name":"node1","view":old_view,"repl_factor":old_repl_factor},
    #         {"subnet":"kv_subnet","host_port":13801,"ip_address":"10.10.0.3","address":"10.10.0.3:13800","name":"node2","view":old_view,"repl_factor":old_repl_factor},
    #         {"subnet":"kv_subnet","host_port":13802,"ip_address":"10.10.0.4","address":"10.10.0.4:13800","name":"node3","view":old_view,"repl_factor":old_repl_factor},
    #         {"subnet":"kv_subnet","host_port":13803,"ip_address":"10.10.0.5","address":"10.10.0.5:13800","name":"node4","view":old_view,"repl_factor":old_repl_factor},
    #     ]

    #     new_shard_count,new_repl_factor,new_nodes = 2,2,["10.10.0.2:13800","10.10.0.3:13800","10.10.0.4:13800","10.10.0.5:13800"]
    #     new_view = ",".join(new_nodes)

    #     self.view_change_helper(old_shard_count,old_nodes,old_ins,new_shard_count,new_repl_factor,new_nodes,new_view,new_ins)

    # def test_view_change_2(self):
    #     old_shard_count,old_repl_factor,old_nodes = 1,2,["10.10.0.2:13800","10.10.0.3:13800"]
    #     old_view = ",".join(old_nodes)

    #     old_ins = [
    #         {"subnet":"kv_subnet","host_port":13800,"ip_address":"10.10.0.2","address":"10.10.0.2:13800","name":"node1","view":old_view,"repl_factor":old_repl_factor},
    #         {"subnet":"kv_subnet","host_port":13801,"ip_address":"10.10.0.3","address":"10.10.0.3:13800","name":"node2","view":old_view,"repl_factor":old_repl_factor},
    #     ]
    #     new_ins = [
    #         {"subnet":"kv_subnet","host_port":13800,"ip_address":"10.10.0.2","address":"10.10.0.2:13800","name":"node1","view":old_view,"repl_factor":old_repl_factor},
    #         {"subnet":"kv_subnet","host_port":13801,"ip_address":"10.10.0.3","address":"10.10.0.3:13800","name":"node2","view":old_view,"repl_factor":old_repl_factor},
    #         {"subnet":"kv_subnet","host_port":13802,"ip_address":"10.10.0.4","address":"10.10.0.4:13800","name":"node3","view":old_view,"repl_factor":old_repl_factor},
    #         {"subnet":"kv_subnet","host_port":13803,"ip_address":"10.10.0.5","address":"10.10.0.5:13800","name":"node4","view":old_view,"repl_factor":old_repl_factor},
    #     ]

    #     new_shard_count,new_repl_factor,new_nodes = 2,2,["10.10.0.2:13800","10.10.0.3:13800","10.10.0.4:13800","10.10.0.5:13800"]
    #     new_view = ",".join(new_nodes)

    #     self.view_change_helper(old_shard_count,old_nodes,old_ins,new_shard_count,new_repl_factor,new_nodes,new_view,new_ins)

    def test_view_change_3(self):
        old_shard_count,old_repl_factor,old_nodes = 1,2,["10.10.0.2:13800","10.10.0.3:13800"]
        old_view = ",".join(old_nodes)

        old_ins = [
            {"subnet":"kv_subnet","host_port":13800,"ip_address":"10.10.0.2","address":"10.10.0.2:13800","name":"node1","view":old_view,"repl_factor":old_repl_factor},
            {"subnet":"kv_subnet","host_port":13801,"ip_address":"10.10.0.3","address":"10.10.0.3:13800","name":"node2","view":old_view,"repl_factor":old_repl_factor},
        ]
        new_ins = [
            {"subnet":"kv_subnet","host_port":13802,"ip_address":"10.10.0.4","address":"10.10.0.4:13800","name":"node3","view":old_view,"repl_factor":old_repl_factor},
            {"subnet":"kv_subnet","host_port":13803,"ip_address":"10.10.0.5","address":"10.10.0.5:13800","name":"node4","view":old_view,"repl_factor":old_repl_factor},
        ]

        new_shard_count,new_repl_factor,new_nodes = 1,2,["10.10.0.4:13800","10.10.0.5:13800"]
        new_view = ",".join(new_nodes)

        self.view_change_helper(old_shard_count,old_nodes,old_ins,new_shard_count,new_repl_factor,new_nodes,new_view,new_ins)

    
if __name__ == '__main__':
    unittest.main()