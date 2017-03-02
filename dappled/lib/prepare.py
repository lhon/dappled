from __future__ import absolute_import, print_function, division, unicode_literals

import os
import subprocess
import sys
import urllib
import zipfile

from dappled.lib import DAPPLED_PATH, ruamel
from dappled.lib.idmap import save_id_mapping
from dappled.lib.notebook import download_notebook_data, write_notebook_data

def call_conda_env_export():
    env = os.environ.copy()
    conda_prefix = os.path.join(os.getcwd(), 'envs')
    env.update(dict(
        CONDA_PREFIX = conda_prefix,
        CONDA_DEFAULT_ENV = 'default'
        ))


    cmd_list = ['conda', 'env', 'export']

    try:
        p = subprocess.Popen(cmd_list, stdout=subprocess.PIPE, stderr=subprocess.PIPE, 
            cwd=conda_prefix, env=env)
    except OSError as e:
        raise Exception("failed to run: %r: %r" % (" ".join(cmd_list), repr(e)))
    (out, err) = p.communicate()
    errstr = err.decode().strip()
    if p.returncode != 0:
        raise Exception('%s: %s' % (" ".join(cmd_list), errstr))
    elif errstr != '':
        for line in errstr.split("\n"):
            print("%s %s: %s" % (cmd_list[0], cmd_list[1], line), file=sys.stderr)
    return out

def setup_published(id):
    if '.' in id:
        path = os.path.join(DAPPLED_PATH, 'nb', id)

        if os.path.exists(path):
            # print(path)
            os.chdir(path)
            return id, False

    data = download_notebook_data(id, include_env=True)

    pvid = '.'.join([data['publish_id'], data['version']])
    path = os.path.join(DAPPLED_PATH, 'nb', pvid)

    save_id_mapping(id, data['publish_id'])

    try: os.makedirs(path)
    except: pass

    write_notebook_data(data, path, write_environment_yml=True)

    os.chdir(path)
    print(path)
    return pvid, True

def download_from_github(args):
    if os.path.exists('dappled.yml'):
        yml = ruamel.yaml.load(open('dappled.yml').read(), ruamel.yaml.RoundTripLoader) 
    else:
        print('dappled.yml not found; please run "dappled init" first')
        sys.exit()

    if not yml.get('github'):
        return False

    github_repo = yml['github']
    url = 'https://github.com/{owner}/{repo}/archive/{sha}.zip'.format(**github_repo)

    filename, headers = urllib.urlretrieve(url)
    with zipfile.ZipFile(filename) as zf:
        prefix = None
        for name in zf.namelist():
            if prefix is None: # assume first entry is the directory name
                prefix = name
                continue
            path = name.replace(prefix, '')
            if path in ('dappled.yml', yml['filename'], 'environment.yml'):
                continue
            with open(path, 'wb') as f:
                f.write(zf.read(name))

