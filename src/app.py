"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
app.py

app.py starts the application
"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
from flask import Flask, request

app = Flask(__name__)

from store import *
from kvs import *
from endpoints import *
from gossip import *

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port='13800')