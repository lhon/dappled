import os
from dappled.lib import requests, HOST, DappledError, ruamel

def download_notebook_data(id, include_env=False):
    params=dict(id=id)

    if include_env:
        from conda.base.context import Context
        context = Context()
        params.update(dict(
            platform = context.platform,
            bits = context.bits,
            ))

    r = requests.get(HOST+'/api/clone', params=params)
    data = r.json()
    if not data['success']:
        raise DappledError(data['message'])

    return data

def write_notebook_data(data, path='', write_environment_yml=False):
    with open(os.path.join(path, 'dappled.yml'), 'w') as f:
        f.write(data['dappled_yml'].encode('utf8'))

    yml = ruamel.yaml.load(data['dappled_yml'], ruamel.yaml.RoundTripLoader) 
    filename = os.path.basename(yml['filename'])
    with open(os.path.join(path, filename), 'w') as f:
        f.write(data['notebook'].encode('utf8'))

    if write_environment_yml:
        with open(os.path.join(path, 'environment.yml'), 'w') as f:
            f.write(data['env'].encode('utf8'))

