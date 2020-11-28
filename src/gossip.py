from flask_apscheduler import APScheduler
import kvs
import requests
import time

class Config(object):
    JOBS = [
        {
            'id': 'gossip',
            'func': 'gossip:gossip',
            'args': (),
            'trigger': 'interval',
            'seconds': 10
        }
    ]

    SCHEDULER_EXECUTORS = {
        'default': {'type': 'threadpool', 'max_workers': 20}
    }

    SCHEDULER_API_ENABLED = True


def gossip():
    for address, data in kvs.state.queue.items():
        if len(data) == 0: continue
        response = requests.put(f'http://{address}/kvs/update', json = data, timeout=2, headers = {"Content-Type": "application/json"})
