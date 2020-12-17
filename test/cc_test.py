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

response_cc = None

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

    view = "10.10.0.2:13800,10.11.0.3:13800"

    buildDockerImage()
    subnetCreate("10.10.0.0/16","kv_subnet")
    subnetCreate("10.11.0.0/16","kv_subnet_2")
    subnetCreate("10.12.0.0/16","kv_subnet_3")

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
        response = requests.put(f'http://localhost:{listOfPorts[0]}/kvs/keys/x', data=payload, timeout=7, headers=headers)
    except:
        print("server at local host " + listOfPorts[1] + " timed out.")

    try:#initializing y
        payload = json.dumps({"value":"init_y", "causal-context":{}})
        response = requests.put(f'http://localhost:{listOfPorts[0]}/kvs/keys/y', data=payload, timeout=7, headers=headers)
    except:
        print("server at local host " + listOfPorts[1] + " timed out.")
    
    #destroy the bridge    
    disconnectFromNetwork("kv_subnet", "node2")
    disconnectFromNetwork("kv_subnet_2", "node1")

    try:#Alice writes "Fuck my life." to y at node1
        payload = json.dumps({"value":"Fuck my life.", "causal-context":{}})
        response = requests.put(f'http://localhost:{listOfPorts[0]}/kvs/keys/y', data=payload, timeout=7, headers=headers)
        response_cc = response.json()["causal-context"]
    except:
        print("server at local host " + listOfPorts[0] + " timed out.")

    try:#Alice reads x from node2(this should be fine)
        payload = json.dumps({"causal-context":response_cc})
        response = requests.get(f'http://localhost:{listOfPorts[1]}/kvs/keys/x', data=payload, timeout=7, headers=headers)
        response_cc = response.json()["causal-context"]
        if response.status_code != 200:
            message = "Read your writes test complete.\n" + "> " + str(response.json())
            printTestResult(message, 0)
    except:
        print("server at local host " + listOfPorts[1] + " timed out.")

    try:#Alice reads y from node2 (should either get "Fuck my life." or a NACK)
        payload = json.dumps({"causal-context":response_cc})
        response = requests.get(f'http://localhost:{listOfPorts[1]}/kvs/keys/y', data=payload, timeout=7, headers=headers)
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

#################################  cc_test_3(Read Your Writes - Delete - Test) ########################################################

    stopAndRemoveAll()
    runInstances(in_)

    #create the bridge
    connectToNetwork("kv_subnet","node2")
    connectToNetwork("kv_subnet_2","node1")

    try:#initializing x
        payload = json.dumps({"value":"init_x", "causal-context":{}})
        response = requests.put(f'http://localhost:{listOfPorts[0]}/kvs/keys/x', data=payload, timeout=7, headers=headers)
    except:
        print("server at local host " + listOfPorts[0] + " timed out.")

    #burn the bridge    
    disconnectFromNetwork("kv_subnet", "node2")
    disconnectFromNetwork("kv_subnet_2", "node1")

    try:#Alice deletes x from node1
        payload = json.dumps({"causal-context":{}})
        response = requests.delete(f'http://localhost:{listOfPorts[0]}/kvs/keys/x', data=payload, timeout=7, headers=headers)
        response_cc = response.json()["causal-context"]
    except:
        print("server at local host " + listOfPorts[0] + " timed out.")

    try:#Alice reads x from node2 (should get 404)
        payload = json.dumps({"causal-context":response_cc})
        response = requests.get(f'http://localhost:{listOfPorts[1]}/kvs/keys/x', data=payload, timeout=7, headers=headers)
        message = "Read your writes - Delete - test complete\n" + "> " + str(response.json())
        if response.status_code == 404:
            printTestResult(message, 1)
        else:
            printTestResult(message, 0)
    except:
        print("server at local host " + listOfPorts[1] + " timed out.")


#################################  cc_test_4(long-chain cc test) ########################################################

    view = "10.10.0.2:13800,10.11.0.3:13800,10.12.0.4:13800"

    Alice_cc = None
    Carol_cc = None
    Bob_cc = None
    Ginger_cc = None

    in_ = [{"subnet":"kv_subnet","host_port":13801,"ip_address":"10.10.0.2","address":"10.10.0.2:13800","name":"node1","view":view,"repl_factor":3}, 
    {"subnet":"kv_subnet_2","host_port":13802,"ip_address":"10.11.0.3","address":"10.11.0.3:13800","name":"node2","view":view,"repl_factor":3},
    {"subnet":"kv_subnet_3","host_port":13803,"ip_address":"10.12.0.4","address":"10.12.0.4:13800","name":"node3","view":view,"repl_factor":3}]

    stopAndRemoveAll()
    runInstances(in_)

    #create the bridge
    connectToNetwork("kv_subnet","node2")
    connectToNetwork("kv_subnet_2","node1")
    connectToNetwork("kv_subnet_3","node2")
    connectToNetwork("kv_subnet_3","node1")
    connectToNetwork("kv_subnet", "node3")
    connectToNetwork("kv_subnet_2", "node3")

    #initializing variables

    try:#initializing x
        payload = json.dumps({"value":"init_x", "causal-context":{}})
        response = requests.put(f'http://localhost:{listOfPorts[0]}/kvs/keys/x', data=payload, timeout=7, headers=headers)
    except:
        print("server at local host " + listOfPorts[0] + " timed out.")

    try:#initializing y
        payload = json.dumps({"value":"init_y", "causal-context":{}})
        response = requests.put(f'http://localhost:{listOfPorts[0]}/kvs/keys/y', data=payload, timeout=7, headers=headers)
    except:
        print("server at local host " + listOfPorts[0] + " timed out.")

    try:#initializing z
        payload = json.dumps({"value":"init_z", "causal-context":{}})
        response = requests.put(f'http://localhost:{listOfPorts[0]}/kvs/keys/z', data=payload, timeout=7, headers=headers)
    except:
        print("server at local host " + listOfPorts[0] + " timed out.")

    try:#initializing w
        payload = json.dumps({"value":"init_w", "causal-context":{}})
        response = requests.put(f'http://localhost:{listOfPorts[0]}/kvs/keys/w', data=payload, timeout=7, headers=headers)
    except:
        print("server at local host " + listOfPorts[0] + " timed out.")

    #destroy the bridge (totally disconnected graph)
    disconnectFromNetwork("kv_subnet","node2")
    disconnectFromNetwork("kv_subnet_2","node1")
    disconnectFromNetwork("kv_subnet_3","node2")
    disconnectFromNetwork("kv_subnet_3","node1")
    disconnectFromNetwork("kv_subnet", "node3")
    disconnectFromNetwork("kv_subnet_2", "node3")

    try:#Alice writes "Bob Smells." to x at node1
        payload = json.dumps({"value":"Bob smells.", "causal-context":{}})
        response = requests.put(f'http://localhost:{listOfPorts[0]}/kvs/keys/x', data=payload, timeout=7, headers=headers)
        Alice_cc = response.json()["causal-context"]
    except:
        print("server at local host " + listOfPorts[0] + " timed out.")

    try:#Bob reads x from node1
        payload = json.dumps({"causal-context":{}})
        response = requests.get(f'http://localhost:{listOfPorts[0]}/kvs/keys/x', data=payload, timeout=7, headers=headers)
        Bob_cc = response.json()["causal-context"]
    except:
        print("server at local host " + listOfPorts[0] + " timed out.")

    try:#Bob writes "Fuck you, Alice." to y at node2
        payload = json.dumps({"value":"Fuck you, Alice.", "causal-context":Bob_cc})
        response = requests.put(f'http://localhost:{listOfPorts[1]}/kvs/keys/y', data=payload, timeout=7, headers=headers)
    except:
        print("server at local host " + listOfPorts[1] + " timed out.")

    try:#Carol reads y from node2
        payload = json.dumps({"causal-context":{}})
        response = requests.get(f'http://localhost:{listOfPorts[1]}/kvs/keys/y', data=payload, timeout=7, headers=headers)
        Carol_cc = response.json()["causal-context"]
    except:
        print("server at local host " + listOfPorts[1] + " timed out.")

    try:#Carol reads x from node2
        payload = json.dumps({"causal-context":Carol_cc})
        response = requests.get(f'http://localhost:{listOfPorts[1]}/kvs/keys/x', data=payload, timeout=7, headers=headers)
        Carol_cc = response.json()["causal-context"]
    except:
        print("server at local host " + listOfPorts[1] + " timed out.")

    try:#Carol writes "What does Bob smell like?" to z at node3
        payload = json.dumps({"value":"What does Bob smell like?", "causal-context":Carol_cc})
        response = requests.put(f'http://localhost:{listOfPorts[2]}/kvs/keys/z', data=payload, timeout=7, headers=headers)
        Carol_cc = response.json()["causal-context"]
    except:
        print("server at local host " + listOfPorts[2] + " timed out.")

    try:#Alice reads z from node3
        payload = json.dumps({"causal-context":Alice_cc})
        response = requests.get(f'http://localhost:{listOfPorts[2]}/kvs/keys/z', data=payload, timeout=7, headers=headers)
        Alice_cc = response.json()["causal-context"]
    except:
        print("server at local host " + listOfPorts[2] + " timed out.")

    try:#Alice writes "Like ass." to w at node1
        payload = json.dumps({"value":"Like ass.", "causal-context":Alice_cc})
        response = requests.put(f'http://localhost:{listOfPorts[0]}/kvs/keys/w', data=payload, timeout=7, headers=headers)
        Alice_cc = response.json()["causal-context"]
    except:
        print("server at local host " + listOfPorts[0] + " timed out.")

    try:#Ginger reads w from node1 (should get "Like ass.")
        payload = json.dumps({"causal-context":{}})
        response = requests.get(f'http://localhost:{listOfPorts[0]}/kvs/keys/w', data=payload, timeout=7, headers=headers)
        Ginger_cc = response.json()["causal-context"]
        message = "Ginger read z, here's what she got:\n" + "> " + str(response.json())
        if response.status_code == 200:
            if response.json()["value"] != "Like ass.":
                printTestResult(message, 0)
        else:
            printTestResults(message, 0)
    except:
        message = "Ginger tried to read w, but the attempt failed due to time out. (long - chain cc test)"
        printTestResult(message, 0)

    try:#Ginger reads z from node2 (should get "What does Bob smell like?" or NACK)
        payload = json.dumps({"causal-context":Ginger_cc})
        response = requests.get(f'http://localhost:{listOfPorts[1]}/kvs/keys/z', data=payload, timeout=7, headers=headers)
        Ginger_cc = response.json()["causal-context"]
        message = "Ginger read z, here's what she got:\n" + "> " + str(response.json())
        if response.status_code == 200:
            if response.json()["value"] != "What does Bob smell like?":
                printTestResult(message, 0)
        if response.status_code == 400:
            if response.json()["error"] != "Unable to satisfy request" or response.json()["message"] != "Error in GET":
                printTestResult(message, 0)
    except:
        message = "Ginger tried to read z, but the attempt failed due to time out. (long - chain cc test)"
        printTestResult(message, 0)

    try:#Ginger reads y from node3 (should get "Fuck you, Alice." or NACK)
        payload = json.dumps({"causal-context":Ginger_cc})
        response = requests.get(f'http://localhost:{listOfPorts[2]}/kvs/keys/y', data=payload, timeout=7, headers=headers)
        Ginger_cc = response.json()["causal-context"]
        message = "Ginger read y, here's what she got:\n" + "> " + str(response.json())
        if response.status_code == 200:
            if response.json()["value"] != "Fuck you, Alice.":
                printTestResult(message, 0)
        if response.status_code == 400:
            if response.json()["error"] != "Unable to satisfy request" or response.json()["message"] != "Error in GET":
                printTestResult(message, 0)
    except:
        message = "Ginger tried to read y, but the attempt failed due to time out (long - chain cc test)."
        printTestResult(message, 0)

    try:#Ginger reads x from node1 (should get "Bob Smells." or NACK)
        payload = json.dumps({"causal-context":Ginger_cc})
        response = requests.get(f'http://localhost:{listOfPorts[0]}/kvs/keys/x', data=payload, timeout=7, headers=headers)
        Ginger_cc = response.json()["causal-context"]
        message = "Ginger read x, here's what she got:\n" + "> " + str(response.json())
        if response.status_code == 200:
            if response.json()["value"] != "Bob smells.":
                printTestResult(message, 0)
        if response.status_code == 400:
            if response.json()["error"] != "Unable to satisfy request" or response.json()["message"] != "Error in GET":
                printTestResult(message, 0)
    except:
        message = "Ginger tried to read x, but the attempt failed due to time out. (long-chain cc test)"
        printTestResult(message, 0)
    

    

    
    



    




    

    




if __name__ == '__main__':
    main()