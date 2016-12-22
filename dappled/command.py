#!/usr/bin/env python2
from __future__ import absolute_import, print_function, division, unicode_literals

import argparse
import json
from getpass import getpass
import os
import re
import string
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

from dappled.lib import DAPPLED_PATH
from dappled.lib.idmap import save_id_mapping, get_id_path
from dappled.lib.kapsel import run_kapsel_command, KapselEnv, DappledError
import dappled.lib.kapsel
dappled.lib.kapsel.patch()

from dappled.lib.utils import get_free_port, get_ip_addresses, watch_conda_install

requests = Session()
if 'DAPPLED_HOST' in os.environ:
    HOST = os.environ['DAPPLED_HOST']
    requests.verify = False
else:
    HOST = 'https://dappled.io'

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
name: Untitled

filename: notebook.ipynb

description:

packages:
- dappled-core

channels:
- http://conda.dappled.io

#downloads:
'''

notebook_ipynb_template = '''
{
 "cells": [
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {
    "collapsed": true
   },
   "outputs": [],
   "source": []
  }
 ],
 "metadata": {
 },
 "nbformat": 4,
 "nbformat_minor": 1
}
'''

def handle_init_action(args):
    if os.path.exists('dappled.yml'):
        yml = ruamel.yaml.load(open('dappled.yml').read(), ruamel.yaml.RoundTripLoader) 
    else:
        print('Creating dappled.yml')
        yml = ruamel.yaml.load(dappled_yml_template, ruamel.yaml.RoundTripLoader)

        notebook_template = json.loads(notebook_ipynb_template)
        if args.language == 'python2':
            notebook_template['metadata']['kernelspec'] = dict(
                display_name="Python 2",
                language="python",
                name="python2",
                )
            yml['packages'].insert(0, 'python=2')
        elif args.language == 'python3':
            notebook_template['metadata']['kernelspec'] = dict(
                display_name="Python 3",
                language="python",
                name="python3",
                )
            yml['packages'].insert(0, 'python=3')
        elif args.language in ('r', 'R'):
            if sys.platform.startswith('linux'):
                yml['packages'].insert(0, 'r-base=3.3.1=1') # https://github.com/jupyter/docker-stacks/issues/210
            yml['packages'].insert(0, 'r-irkernel')
            yml['channels'].insert(0, 'r')

            notebook_template['metadata']['kernelspec'] = dict(
                display_name="R",
                language="R",
                name="ir",
                )
        else:
            assert False

    if not yml.get('filename'):
        yml['filename'] = 'notebook.ipynb'
    filename = yml['filename']
    if not os.path.exists(filename):
        print('Creating', filename)
        with open(filename, 'w') as f:
            print(json.dumps(notebook_template), file=f)

    with open('dappled.yml', 'w') as f:
        print(ruamel.yaml.dump(yml, Dumper=ruamel.yaml.RoundTripDumper), file=f)

    kapsel_env = KapselEnv()

def handle_edit_action(args):
    if handle_if_docker_request(args):
        return

    if os.path.exists('dappled.yml'):
        yml = ruamel.yaml.load(open('dappled.yml').read(), ruamel.yaml.RoundTripLoader) 
    else:
        print('dappled.yml not found; please run "dappled init" first')
        sys.exit()

    if 'filename' not in yml:
        print('"filename" field not found in dappled.yml; please specify a notebook')
        sys.exit()

    filename = yml['filename']
    if filename is None:
        print("Please specify a filename in dappled.yml")
        sys.exit()
    if not os.path.exists(filename):
        print('"%s" not found; please fix "filename" in dappled.yml')
        sys.exit()

    # if connecting over SSH, then require server mode
    if ('SSH_CONNECTION' in os.environ or 'SSH_CLIENT' in os.environ) and not args.local:
        print('SSH connection detected; using --remote (--local to override)')
        args.remote = True
    if args.local:
        args.remote = False

    kapsel_env = KapselEnv()
    options = []
    # options.append('--log-level=ERROR')
    options.append('''--NotebookApp.nbserver_extensions={'dappled_core.nbserver_extension':True}''')

    # locate free port
    port = get_free_port(args.port, 50)
    if port is not None:
        options.append('--port=%d' % port)
    else:
        print('Failed to get free port')
        sys.exit()

    # handle --remote and identify URLs/ip addresses
    if args.remote:
        hashed_password = kapsel_env.run('python', '-c', 
            'import getpass,IPython.lib;print(IPython.lib.passwd(getpass.getpass("Create a password for editing notebook: ")))')
        options.append('--NotebookApp.password=%s' % hashed_password)

        ip_addresses = get_ip_addresses()
        options.append('--ip=0.0.0.0')
        # options.append('--no-browser') # didn't seem to work
        options.append('--browser=echo')
        print('Notebook URLs:')
    else:
        ip_addresses = ['localhost']
        print('Opening this URL:')

    for ip in ip_addresses:
        print('  http://%s:%d/notebooks/%s' % (ip, port, filename))

    run_kapsel_command('run', filename, *options)

def handle_run_action(args, unknown_args):

    if args.id is not None:
        path = get_id_path(args.id)

        if path is None:
            handle_prepare_action(args, show_run=False)
            path = get_id_path(args.id)
            if path is None:
                raise DappledError('%s is not a valid ID' % args.id)

        os.chdir(path)

    if handle_if_docker_request(args):
        return

    # run_kapsel_command('run', 'dappled-run')
    kapsel_env = KapselEnv()
    cmd_list = ['dappled-run'] + unknown_args
    kapsel_env.run(*cmd_list, print_stdout=True)

def handle_publish_action(args):

    options = dict(
        username=raw_input('Username: '),
        password=getpass(),
        )

    yml = ruamel.yaml.load(open('dappled.yml').read(), ruamel.yaml.RoundTripLoader) 
    notebook_filename = yml['filename']

    # kapsel_env = KapselEnv()

    multiple_files = [
        ('options', ('options.json', json.dumps(options), 'application/json')),
        ('dappled.yml', ('dappled.yml', open('dappled.yml', 'rb').read(), 'text/x-yaml')),
        ('notebook.ipynb', (notebook_filename, open(notebook_filename, 'rb').read(), 'application/json')),
        ('environment.yml', ('environment.yml', call_conda_env_export(), 'text/x-yaml')),
    ]
    r = requests.post(HOST+'/api/publish', files=multiple_files)
    rj = r.json()
    if rj['success']:
        yml['publish_id'] = rj['publish_id']
        with open('dappled.yml', 'w') as f:
            print(ruamel.yaml.dump(yml, Dumper=ruamel.yaml.RoundTripDumper), file=f)
        print('Published as', rj['publish_id'], 'version', rj['version'])
    else:
        print(rj['message'])

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
        print(data['dappled_yml'], file=f)

    yml = ruamel.yaml.load(data['dappled_yml'], ruamel.yaml.RoundTripLoader) 
    filename = os.path.basename(yml['filename'])
    with open(os.path.join(path, filename), 'w') as f:
        print(data['notebook'], file=f)

    if write_environment_yml:
        with open(os.path.join(path, 'environment.yml'), 'w') as f:
            print(data['env'], file=f)

def setup_published(id):
    if '.' in id:
        path = os.path.join(DAPPLED_PATH, 'nb', id)

        if os.path.exists(path):
            # print(path)
            os.chdir(path)
            return id

    data = download_notebook_data(id, include_env=True)

    pvid = '.'.join([data['publish_id'], data['version']])
    path = os.path.join(DAPPLED_PATH, 'nb', pvid)

    save_id_mapping(id, data['publish_id'])

    try: os.makedirs(path)
    except: pass

    write_notebook_data(data, path, write_environment_yml=True)

    os.chdir(path)
    print(path)
    return pvid

def handle_prepare_action(args, show_run=True):

    if args.id is not None:
        id = setup_published(args.id)
        sys.argv = [id if x==args.id else x for x in sys.argv] # replace with updated id, in case docker is requested

        cmd_list = ['python', '-u', '-m', 'conda', 'env', 'create', '-f', 'environment.yml', '-p', 'envs/default']
        try:
            p = subprocess.Popen(cmd_list, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        except OSError as e:
            raise CondaError("failed to run: %r: %r" % (" ".join(cmd_list), repr(e)))

        out = watch_conda_install(p)

    if handle_if_docker_request(args): return

    kapsel_env = KapselEnv()

    if args.id is not None and show_run:
        print(args.id, 'is ready. To run this notebook use this command:')
        print()
        print('   dappled run', args.id)
        print()

def handle_clone_action(args):
    if os.path.exists('dappled.yml'):
        print('dappled.yml already found in current directory... aborting')
        sys.exit()

    data = download_notebook_data(args.id)

    if not args.include_env:
        write_notebook_data(data)
    else:
        write_notebook_data(data, write_environment_yml=True)
        cmd_list = ['python', '-u', '-m', 'conda', 'env', 'create', '-f', 'environment.yml', '-p', 'envs/default']
        try:
            p = subprocess.Popen(cmd_list, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        except OSError as e:
            raise CondaError("failed to run: %r: %r" % (" ".join(cmd_list), repr(e)))

        out = watch_conda_install(p)

def handle_clean_action(args):
    run_kapsel_command('clean')

def handle_if_docker_request(args):
    if 'DOCKER_IMAGE' in os.environ:
        return False # already in container

    if args.no_docker:
        return False

    if os.path.exists('dappled.yml'):
        yml = ruamel.yaml.load(open('dappled.yml').read(), ruamel.yaml.RoundTripLoader) 
    else:
        print('dappled.yml not found; please run "dappled init" first')
        sys.exit()

    if not yml.get('docker_image'):
        return False

    docker_image = yml['docker_image']
    print('dappled.yml specifies docker image "%s"' % docker_image)

    if not sys.platform.startswith('linux'):
        print('Docker/udocker support requires linux')
        print('You can try rerunning with the --no-docker flag')
        sys.exit()

    def run_cmd(cmd):

        import signal
        original_sigint = signal.getsignal(signal.SIGINT)

        # http://stackoverflow.com/a/18115530/5679888
        # http://stackoverflow.com/a/32222971/5679888
        def exit_gracefully(signum, frame):
            # restore the original signal handler as otherwise evil things will happen
            # in raw_input when CTRL+C is pressed, and our signal handler is not re-entrant
            signal.signal(signal.SIGINT, original_sigint)

            try:
                if raw_input("\nReally quit? (y/n)> ").lower().startswith('y'):
                    os.killpg(pgrp, signal.SIGTERM)
                    # proc.send_signal(signal.SIGTERM)
                    sys.exit(1)

            except KeyboardInterrupt:
                print("Ok ok, quitting")
                os.killpg(pgrp, signal.SIGTERM)
                sys.exit(1)

            # restore the exit gracefully handler here    
            signal.signal(signal.SIGINT, exit_gracefully)


        signal.signal(signal.SIGINT, exit_gracefully)
        proc = subprocess.Popen(cmd, shell=False, stdin=subprocess.PIPE, preexec_fn=os.setsid)
        pgrp = os.getpgid(proc.pid)

        # http://stackoverflow.com/a/33277846/5679888
        proc.communicate()

    # get docker image
    output = subprocess.check_output(['udocker.py', 'images'])
    images = [x.split()[0] for x in output.strip().split('\n')[1:]]
    if docker_image not in images:
        print('Pulling docker image...')
        run_cmd(['udocker.py', 'pull', docker_image])

    # create a container from the docker image (intended to be unmutable)
    container_name = 'dpl:' + docker_image[-26:] # udocker max name length is 30
    output = subprocess.check_output(['udocker.py', 'ps'])
    if container_name not in output:
        print("Creating container...")
        run_cmd(['udocker.py', 'create', '--name='+container_name, docker_image])

    # run dappled command within udocker container
    udocker_cmd = ['udocker.py', 'run', 
            '--hostauth', '--hostenv', '--bindhome', '--volume=/run', 
            '--user=%s' % os.environ['USER'], '--workdir=%s' % os.environ['PWD'], 
            container_name, 
            ]

    cmd_str = ' '.join('"%s"' % x if ' ' in x else x for x in sys.argv)
    # - udocker.py-invoked executable needs to exist inside the image, so let's use bash
    # - PATH isn't passed through udocker.py correctly so do it manually
    # - command needs to be a single argument
    udocker_cmd.append("""bash -c 'PATH="%s" %s'""" % (os.environ['PATH'], cmd_str))

    print('Launching udocker...')

    os.environ['DOCKER_IMAGE'] = docker_image
    run_cmd(udocker_cmd)

    print('exited udocker')

    return True

def handle_install_action(args):
    cmd_list = ['add-packages'] 
    if args.channel:
        for c in args.channel:
            cmd_list.extend(['-c', c])
    cmd_list.extend(args.packages)
    run_kapsel_command(*cmd_list)

def handle_name_action(args):
    allowed_name = r'[a-z][a-z0-9-]+$'

    if args.shortname[0] not in string.ascii_lowercase:
        print('"{}" does not start with an undercase letter'.format(args.shortname))
        sys.exit()

    if not re.match(allowed_name, args.shortname):
        print('"{}" must consist only of undercase letters, numbers, and dashes'.format(args.shortname))
        sys.exit()

    options = dict(
        username=raw_input('Username: '),
        password=getpass(),
        id=args.id,
        shortname=args.shortname,
        )

    r = requests.post(HOST+'/api/name', data=options)
    rj = r.json()
    print(rj['message'])

class ArgumentParser(argparse.ArgumentParser):
    def print_help(self):
        super(ArgumentParser, self).print_help()

        if self.prog == 'dappled' and sys.argv[1:] in ([], ['help'], ['-h'], ['--help']):
            print("""
Example Commands
----------------

# Installing and running a published notebook
dappled run dappled/hello

# Cloning, editing, and running a published notebook
mkdir hello && cd hello
dappled clone dappled/hello
dappled edit
dappled run

# Creating, editing, and publishing a new project and notebook
mkdir test && cd test
dappled init
dappled edit
dappled publish

# Installing a conda package
dappled install matplotlib
""")

def main():
    parser = ArgumentParser(description="dappled is a tool for creating, editing, and publishing deployable notebooks")
    subparsers = parser.add_subparsers(dest='dappled_action', metavar='command')
    # parser.add_argument("-v", ...)

    init_parser = subparsers.add_parser("init", help="Initialize a new dappled directory")
    init_parser.add_argument('--language', type=str, default='python2')

    edit_parser = subparsers.add_parser("edit", help="Edit the Jupyter Notebook specified by dappled.yml")
    edit_parser.add_argument('--no-docker', action="store_true")
    edit_parser.add_argument('--remote', action="store_true")
    edit_parser.add_argument('--local', action="store_true")
    edit_parser.add_argument('--port', type=int, default=8888)

    run_parser = subparsers.add_parser("run", help="Run a dappled notebook")
    run_parser.add_argument("id", nargs='?')
    run_parser.add_argument('--no-docker', action="store_true")
    # run_parser.add_argument('--port', type=int, default=8008)
    # run_parser.add_argument('--server', action="store_true")

    publish_parser = subparsers.add_parser("publish", help="Publish a notebook to dappled.io")

    prepare_parser = subparsers.add_parser("prepare", help="Prepare an environment specified by dappled.yml")
    prepare_parser.add_argument("id", nargs='?')
    prepare_parser.add_argument('--no-docker', action="store_true")

    clone_parser = subparsers.add_parser("clone", help="Clone a published notebook into the current directory")
    clone_parser.add_argument("id")
    clone_parser.add_argument('--include-env', action="store_true")

    clean_parser = subparsers.add_parser("clean", help="Clean current software environment")

    install_parser = subparsers.add_parser("install", help="Install a conda package and record it at dappled.yml")
    install_parser.add_argument("packages", nargs="+")
    install_parser.add_argument('--channel', '-c', action='append')

    name_parser = subparsers.add_parser("name", help="Assign a published notebook a short id")
    name_parser.add_argument("id")
    name_parser.add_argument("shortname")

    # a_parser.add_argument("something", choices=['a1', 'a2'])

    if len(sys.argv) == 1:
        sys.argv.append('-h')

    args, unknown_args = parser.parse_known_args()
    if args.dappled_action != 'run':
        args = parser.parse_args()

    try:
        if args.dappled_action == 'init':
            handle_init_action(args)
        elif args.dappled_action == 'edit':
            handle_edit_action(args)
        elif args.dappled_action == 'run':
            handle_run_action(args, unknown_args)
        elif args.dappled_action == 'publish':
            handle_publish_action(args)
        elif args.dappled_action == 'prepare':
            handle_prepare_action(args)
        elif args.dappled_action == 'clone':
            handle_clone_action(args)
        elif args.dappled_action == 'clean':
            handle_clean_action(args)
        elif args.dappled_action == 'install':
            handle_install_action(args)
        elif args.dappled_action == 'name':
            handle_name_action(args)
    except DappledError as e:
        print(e)


if __name__ == '__main__':
    main()
