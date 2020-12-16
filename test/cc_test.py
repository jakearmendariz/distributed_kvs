from requests.exceptions import Timeout
import requests
import asyncio
import json
import random
import string
import time
import os
import sys
import json
from termcolor import colored

#list of relevant ports
listOfPorts = ["13801", "13802", "13803", "13804"]

def printTestResult(message, flag):
    
    pass_string = "###############################################\n" + message + "\n" + colored("Pass", "green") + "\n###############################################"
    fail_string = "###############################################\n" + message + "\n" + colored("Fail", "red") + "\n###############################################"
    
    if flag == 1:
        print(pass_string)
    else:
        print(fail_string)    

def removeSubnet(subnetName):
    command = "docker network rm " + subnetName
    os.system(command)
    time.sleep(2)

def subnetCreate(subnetAddress, subnetName):
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

def main():

    response_cc = None

    view = "10.10.0.2:13800,10.11.0.3:13800"

    buildDockerImage()
    subnetCreate("10.10.0.0/16","kv_subnet")
    subnetCreate("10.11.0.0/16","kv_subnet_2")

    in_ = [{"subnet":"kv_subnet","host_port":13801,"ip_address":"10.10.0.2","address":"10.10.0.2:13800","name":"node1","view":view,"repl_factor":2}, 
    {"subnet":"kv_subnet_2","host_port":13802,"ip_address":"10.11.0.3","address":"10.11.0.3:13800","name":"node2","view":view,"repl_factor":2}]

    ###################                      cc_test_1(variation on test 7 from test_public.py)                    #######################
    
    stopAndRemoveAll()
    runInstances(in_)

    #create the bridge
    connectToNetwork("kv_subnet","node2")
    connectToNetwork("kv_subnet_2","node1")
    
    headers   = {'content-type':'application/json'}

    try:#initializing x to node 2
        payload = json.dumps({"value":"init_x", "causal-context":{}})
        response = requests.put(f'http://localhost:{listOfPorts[1]}/kvs/keys/x', data=payload, timeout=6, headers=headers)
    except:
        print("server at local host " + listOfPorts[1] + " timed out.")
    
    #now remove the bridge in such a way that the two nodes are not left without a network 
    # to exist on, but they can no longer communicate with each other (create partition)
    disconnectFromNetwork("kv_subnet", "node2")
    disconnectFromNetwork("kv_subnet_2", "node1")

    try: #Alice writes "Bob Smells" to x at node1
        payload   = json.dumps({"value":"Bob Smells", "causal-context":{}})
        response = requests.put(f'http://localhost:{listOfPorts[0]}/kvs/keys/x', data=payload, timeout=6, headers=headers)
    except requests.exceptions.Timeout:
        print("server at local host " + listOfPorts[0] + " timed out.")

    try:#Bob reads x from node1
        payload = json.dumps({"causal-context":{}})
        response = requests.get(f'http://localhost:{listOfPorts[0]}/kvs/keys/x', data=payload, timeout=6, headers=headers)
        response_cc = response.json()["causal-context"]
    except requests.exceptions.Timeout:
        print("server at local host" + listOfPorts[0] + " timed out.")

    try:#Bob writes "Fuck you, Alice" to y at node2
        payload = json.dumps({"value":"Fuck you, Alice", "causal-context":response_cc})
        response = requests.put(f'http://localhost:{listOfPorts[1]}/kvs/keys/y', data=payload, timeout=6, headers=headers)
    except requests.exceptions.Timeout:
        print("server at local host " + listOfPorts[1] + " timed out.")

    try:#Carol reads y from node2
        payload = json.dumps({"causal-context":{}})
        response = requests.get(f'http://localhost:{listOfPorts[1]}/kvs/keys/y', data=payload, timeout=6, headers=headers)
        response_cc = response.json()["causal-context"]
    except:
        print("server at local host " + listOfPorts[1] + " timed out.")
    
    try:#Here's where it varies from test 7; Carol writes "I am Carol, hear me roar" to z at node2
        payload = json.dumps({"value": "I am Carol, hear me roar", "causal-context":response_cc})
        response = requests.put(f'http://localhost:{listOfPorts[1]}/kvs/keys/z', data=payload, timeout=6, headers=headers)
        response_cc = response.json()["causal-context"]
    except:
        print("server at local host " + listOfPorts[1] + " timed out.")

    try:#Carol finally tries to read x from node2
        payload = json.dumps({"causal-context":response_cc})
        response = requests.get(f'http://localhost:{listOfPorts[1]}/kvs/keys/x', data=payload, timeout=6, headers=headers)
        message = "Test 1 basic causal consistency test complete:\n " + "> " + str(response.json())
        if response.status_code == 200:
            verdict = (response.json()["value"] == "Bob Smells")
            printTestResult(message, 1) if verdict else printTestResult(message, 0)
        elif response.status_code == 400:
            error = response.json()["error"]
            mess  = response.json()["message"]
            printTestResult(message, 1) if (mess == "Error in GET" and error == "Unable to satisfy request") else printTestResult(message, 0)
        else:
            printTestResults(message, 0)
    except:
        print("server at local host " + listOfPorts[1] + " timed out.")

#################################  cc_test_2(Read Your Writes Test) ########################################################

    stopAndRemoveAll()
    runInstances(in_)

    #create the bridge
    connectToNetwork("kv_subnet","node2")
    connectToNetwork("kv_subnet_2","node1")

    #initialize x and y

    try:#initializing x
        payload = json.dumps({"value":"init_x", "causal-context":{}})
        response = requests.put(f'http://localhost:{listOfPorts[0]}/kvs/keys/x', data=payload, timeout=6, headers=headers)
    except:
        print("server at local host " + listOfPorts[1] + " timed out.")

    try:#initializing y
        payload = json.dumps({"value":"init_y", "causal-context":{}})
        response = requests.put(f'http://localhost:{listOfPorts[0]}/kvs/keys/y', data=payload, timeout=6, headers=headers)
    except:
        print("server at local host " + listOfPorts[1] + " timed out.")
    
    #destroy the bridge    
    disconnectFromNetwork("kv_subnet", "node2")
    disconnectFromNetwork("kv_subnet_2", "node1")

    try:#Alice writes "Fuck my life." to y at node1
        payload = json.dumps({"value":"Fuck my life.", "causal-context":{}})
        response = requests.put(f'http://localhost:{listOfPorts[0]}/kvs/keys/y', data=payload, timeout=6, headers=headers)
        response_cc = response.json()["causal-context"]
    except:
        print("server at local host " + listOfPorts[0] + " timed out.")

    try:#Alice reads x from node2(this should be fine)
        payload = json.dumps({"causal-context":response_cc})
        response = requests.get(f'http://localhost:{listOfPorts[1]}/kvs/keys/x', data=payload, timeout=6, headers=headers)
        response_cc = response.json()["causal-context"]
        if response.status_code != 200:
            message = "Read your writes test complete.\n" + "> " + str(response.json())
            printTestResult(message, 0)
    except:
        print("server at local host " + listOfPorts[1] + " timed out.")

    try:#Alice reads y from node2 (should either get "Fuck my life." or a NACK)
        payload = json.dumps({"causal-context":response_cc})
        response = requests.get(f'http://localhost:{listOfPorts[1]}/kvs/keys/y', data=payload, timeout=6, headers=headers)
        response_cc = response.json()["causal-context"]
        message = "Read your writes test complete.\n" + "> " + str(response.json())
        if response.status_code == 200:
            verdict = (response.json()["value"] == "Fuck my life.")
            printTestResult(message, 1) if verdict else printTestResult(message, 0)
        if response.status_code == 400:
            verdict1 = (response.json()["error"] == "Unable to satisfy request")
            verdict2 = (response.json()["message"] == "Error in GET")
            printTestResult(message, 1) if (verdict1 and verdict2) else printTestResult(message, 0)
        else:
            printTestResults(message, 0) 
    except:
        print("server at local host " + listOfPorts[1] + " timed out.")


if __name__ == '__main__':
    main()