#!/usr/bin/env python2
from __future__ import absolute_import, print_function, division, unicode_literals

import argparse
import json
from getpass import getpass
import os
import subprocess
import uuid

import appdirs
from requests import Session
try:
    import ruamel.yaml
except:
    # handle the conda version of ruamel_yaml that has an underscore
    import imp, sys
    import ruamel_yaml
    ruamel = imp.new_module('ruamel')
    ruamel.yaml = sys.modules['ruamel.yaml'] = ruamel_yaml

from lib.kapsel import run_kapsel_command, KapselEnv
import lib.kapsel
lib.kapsel.patch()

requests = Session()
if 'DAPPLED_HOST' in os.environ:
    HOST = os.environ['DAPPLED_HOST']
    requests.verify = False
else:
    HOST = 'https://dappled.io'
DAPPLED_PATH = appdirs.user_cache_dir('dappled') # user_data_dir has space on OSX

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

dappled_yml_template = '''
name:

filename:

description:
'''

def handle_init_action(args):
    if os.path.exists('dappled.yml'):
        yml = ruamel.yaml.load(open('dappled.yml').read(), ruamel.yaml.RoundTripLoader) 
    else:
        yml = ruamel.yaml.load(dappled_yml_template)

    if 'notebook_id' not in yml:
        yml['notebook_id'] = str(uuid.uuid4())

    with open('dappled.yml', 'w') as f:
        print(ruamel.yaml.dump(yml, Dumper=ruamel.yaml.RoundTripDumper), file=f)

def handle_edit_action(args):
    if os.path.exists('dappled.yml'):
        yml = ruamel.yaml.load(open('dappled.yml').read(), ruamel.yaml.RoundTripLoader) 
    else:
        print('dappled.yml not found; please run "dappled init" first')
        sys.exit()

    if 'filename' not in yml:
        print('"filename" field not found in dappled.yml; please specify a notebook')
        sys.exit()

    filename = yml['filename']
    if not os.path.exists(filename):
        print('"%s" not found; please fix "filename" in dappled.yml')
        sys.exit()

    run_kapsel_command('run', filename)

def handle_run_action(args):
    run_kapsel_command('run', 'dappled-run')

def handle_publish_action(args):

    username = raw_input('Username: ')
    password = getpass()

    options = dict(
        username=username,
        password=password,
        )

    yml = ruamel.yaml.load(open('dappled.yml').read(), ruamel.yaml.RoundTripLoader) 
    notebook_filename = yml['filename']

    multiple_files = [
        ('options', ('options.json', json.dumps(options), 'application/json')),
        ('dappled.yml', ('dappled.yml', open('dappled.yml', 'rb').read(), 'text/x-yaml')),
        # ('kapsel.yml', ('kapsel.yml', open('kapsel.yml', 'rb').read(), 'text/x-yaml')),
        ('notebook.ipynb', (notebook_filename, open(notebook_filename, 'rb').read(), 'application/json')),
        ('environment.yml', ('environment.yml', call_conda_env_export(), 'text/x-yaml')),
    ]
    requests.post(HOST+'/api/publish', files=multiple_files)

def download_notebook_data(id):
    if not id:
        print('need to specify a notebook to clone')
        sys.exit()

    r = requests.get(HOST+'/api/clone', params=dict(
        id=id
        ))
    data = r.json()

    return data

def write_notebook_data(data, path=''):
    with open(os.path.join(path, 'dappled.yml'), 'w') as f:
        print(data['dappled_yml'], file=f)
    # with open(os.path.join(path, 'kapsel.yml'), 'w') as f:
    #     print(data['kapsel_yml'], file=f)

    yml = ruamel.yaml.load(data['dappled_yml'], ruamel.yaml.RoundTripLoader) 
    filename = os.path.basename(yml['filename'])
    with open(os.path.join(path, filename), 'w') as f:
        print(data['notebook'], file=f)

def handle_prepare_action(args):
    if args.id is not None:
        data = download_notebook_data(args.id)

        id = '.'.join([data['publish_id'], data['version']])
        path = os.path.join(DAPPLED_PATH, 'nb', id)

        try: os.makedirs(path)
        except: pass

        write_notebook_data(data, path)
        os.chdir(path)

    # os.system('conda kapsel prepare')
    # run_kapsel_command('prepare')
    kapsel_env = KapselEnv()
    dappled_core_path = os.path.dirname(kapsel_env.run('python', '-c', 'import dappled_core; print(dappled_core.__file__)'))
    nbextension_path = os.path.join(dappled_core_path, 'static', 'nbextension')
    kapsel_env.run('jupyter', 'nbextension', 'install', nbextension_path, '--sys-prefix', '--symlink')
    kapsel_env.run('jupyter', 'nbextension', 'enable', 'nbextension/nbextension', '--sys-prefix')

    kapsel_env.run('jupyter', 'dashboards', 'quick-setup', '--sys-prefix', '--InstallNBExtensionApp.log_level=CRITICAL')

def handle_clone_action(args):
    if os.path.exists('dappled.yml'):
        print('dappled.yml already found in current directory... aborting')
        sys.exit()

    data = download_notebook_data(args.id)

    write_notebook_data(data)


def main():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest='dappled_action', help='dappled actions')
    # parser.add_argument("-v", ...)

    init_parser = subparsers.add_parser("init")
    edit_parser = subparsers.add_parser("edit")
    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("id", nargs='?')
    publish_parser = subparsers.add_parser("publish")
    prepare_parser = subparsers.add_parser("prepare")
    prepare_parser.add_argument("id", nargs='?')
    clone_parser = subparsers.add_parser("clone")
    clone_parser.add_argument("id")

    # a_parser.add_argument("something", choices=['a1', 'a2'])

    args = parser.parse_args()

    # print(args)

    if args.dappled_action == 'init':
        handle_init_action(args)
    elif args.dappled_action == 'edit':
        handle_edit_action(args)
    elif args.dappled_action == 'run':
        handle_run_action(args)
    elif args.dappled_action == 'publish':
        handle_publish_action(args)
    elif args.dappled_action == 'prepare':
        handle_prepare_action(args)
    elif args.dappled_action == 'clone':
        handle_clone_action(args)


if __name__ == '__main__':
    main()
