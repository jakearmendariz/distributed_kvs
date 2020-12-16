"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
app.py

app.py starts the application, all functionality exists in kvs.py and proxy.py
"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
from flask import Flask, request

app = Flask(__name__)

from view_change import *
from kvs import *
from endpoints import *
from gossip import *

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port='13800')