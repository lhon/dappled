import os

if os.name == 'nt':
    import appdirs
    DAPPLED_PATH = appdirs.user_data_dir('dappled')
else:
    DAPPLED_PATH = os.path.expanduser('~/.dappled')

try:
    os.makedirs(DAPPLED_PATH)
except:
    pass

class DappledError(Exception):
    pass

try:
    import ruamel.yaml
except:
    # handle the conda version of ruamel_yaml that has an underscore
    import imp, sys
    import ruamel_yaml
    ruamel = imp.new_module('ruamel')
    ruamel.yaml = sys.modules['ruamel.yaml'] = ruamel_yaml
    
from requests import Session
requests = Session()
if 'DAPPLED_HOST' in os.environ:
    HOST = os.environ['DAPPLED_HOST']
    requests.verify = False
else:
    HOST = 'https://dappled.io'

