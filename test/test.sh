docker build -t kvs:4.0 .

docker stop node1 node2 node3 node4
docker rm node1 node2 node3 node4

docker run -p 13800:13800 --net=kv_subnet --ip=10.10.0.2 --name="node1" -e ADDRESS="10.10.0.2:13800" -e VIEW="10.10.0.2:13800,10.10.0.3:13800,10.10.0.4:13800,10.10.0.5:13800" -e REPL_FACTOR=2 kvs:4.0 & 

docker run -p 13801:13800 --net=kv_subnet --ip=10.10.0.3 --name="node2" -e ADDRESS="10.10.0.3:13800" -e VIEW="10.10.0.2:13800,10.10.0.3:13800,10.10.0.4:13800,10.10.0.5:13800" -e REPL_FACTOR=2 kvs:4.0 & 

docker run -p 13802:13800 --net=kv_subnet --ip=10.10.0.4 --name="node3" -e ADDRESS="10.10.0.4:13800" -e VIEW="10.10.0.2:13800,10.10.0.3:13800,10.10.0.4:13800,10.10.0.5:13800" -e REPL_FACTOR=2 kvs:4.0 & 

docker run -p 13803:13800 --net=kv_subnet --ip=10.10.0.5 --name="node4" -e ADDRESS="10.10.0.5:13800" -e VIEW="10.10.0.2:13800,10.10.0.3:13800,10.10.0.4:13800,10.10.0.5:13800" -e REPL_FACTOR=2 kvs:4.0 & 

sleep 5;

python3 test/replica_test.py

docker stop node1 node2 node3 node4
docker rm node1 node2 node3 node4