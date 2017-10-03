"""Simple run test for laconic framework"""
#import os
import sys
sys.path.append("/home/iota/Projects/laconic")
from laconic import Laconic

app = Laconic(__name__)

@app.route('/')
def hello() -> str:
    return 'hello'


if __name__ == '__main__':
    app.run()
