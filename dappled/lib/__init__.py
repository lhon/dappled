import os

if os.name == 'nt':
    DAPPLED_PATH = appdirs.user_data_dir('dappled')
else:
    DAPPLED_PATH = os.path.expanduser('~/.dappled')


class DappledError(Exception):
    pass

