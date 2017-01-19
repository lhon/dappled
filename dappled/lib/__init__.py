import os

if os.name == 'nt':
    DAPPLED_PATH = appdirs.user_data_dir('dappled')
else:
    DAPPLED_PATH = os.path.expanduser('~/.dappled')

try:
    os.makedirs(DAPPLED_PATH)
except:
    pass

class DappledError(Exception):
    pass

