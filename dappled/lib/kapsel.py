from __future__ import absolute_import, print_function
import os
import subprocess
import sys
from dappled.lib.utils import unbuffered, watch_conda_install, which

class DappledError(Exception):
    pass

def patch():
    # use dappled.yml instead of kapsel.yml
    from conda_kapsel.project_file import ProjectFile
    @classmethod
    def load_for_directory(cls, directory):
        return ProjectFile(os.path.join(directory, 'dappled.yml'))

    ProjectFile.load_for_directory = load_for_directory

    def ProjectFile_load(self):
        self.orig_load()

        self.injected_env_specs = False
        if 'env_specs' not in self._yaml:
            self.injected_env_specs = True
            self._yaml['env_specs'] = dict(default=dict(channels=[], packages=[]))

        if 'commands' not in self._yaml:
            self._yaml['commands'] = {}
        self._yaml['commands']['dappled-run'] = dict(
            env_spec='default',
            unix='dappled-run'
            )
    ProjectFile.orig_load = ProjectFile.load
    ProjectFile.load = ProjectFile_load

    def ProjectFile_save(self):
        # assume save only called once...
        if self.injected_env_specs:
            del self._yaml['env_specs']

        del self._yaml['commands']

        self.orig_save()
    ProjectFile.orig_save = ProjectFile.save
    ProjectFile.save = ProjectFile_save

    # hides extra messages
    def prepare_main(args):
        """Start the prepare command and return exit status code."""
        from conda_kapsel.commands.prepare import prepare_command
        if prepare_command(args.directory, args.mode, args.env_spec):
            # print("The project is ready to run commands.")
            # print("Use `conda-kapsel list-commands` to see what's available.")
            return 0
        else:
            return 1
    import conda_kapsel.commands.prepare
    conda_kapsel.commands.prepare.main = prepare_main

    # patch handles deprecation warning: ...bin/pip list: DEPRECATION: The default format will switch
    # to columns in the future. You can use --format=(legacy|columns) (or define a
    # format=(legacy|columns) in your pip.conf under the [list] section) to disable this
    # warning.
    def installed(prefix):
        import re
        from conda_kapsel.internal.pip_api import PipNotInstalledError, _call_pip
        """Get a dict of package names to (name, version) tuples."""
        if not os.path.isdir(prefix):
            return dict()
        try:
            out = _call_pip(prefix, extra_args=['list', '--format=legacy']).decode('utf-8')
            # on Windows, $ in a regex doesn't match \r\n, we need to get rid of \r
            out = out.replace("\r\n", "\n")
        except PipNotInstalledError:
            out = ""  # if pip isn't installed, there are no pip packages
        # the output to parse looks like:
        #   ympy (0.7.6.1)
        #   tables (3.2.2)
        #   terminado (0.5)
        line_re = re.compile("^ *([^ ]+) *\(([^)]+)\)$", flags=re.MULTILINE)
        result = dict()
        for match in line_re.finditer(out):
            result[match.group(1)] = (match.group(1), match.group(2))
        return result
    import conda_kapsel.internal.pip_api
    conda_kapsel.internal.pip_api.installed = installed

    # allows explicit python=2/3 specification
    def fix_environment_deviations(self, prefix, spec, deviations=None):
        import os

        from conda_kapsel.conda_manager import CondaManager, CondaEnvironmentDeviations, CondaManagerError
        import conda_kapsel.internal.conda_api as conda_api
        import conda_kapsel.internal.pip_api as pip_api

        if deviations is None:
            deviations = self.find_environment_deviations(prefix, spec)

        # command_line_packages = set(['python']).union(set(spec.conda_packages))
        command_line_packages = set(spec.conda_packages)
        if ('python' not in command_line_packages and 
            not any(x.startswith('python=') for x in command_line_packages)
            ):
            command_line_packages.add('python')

        if os.path.isdir(os.path.join(prefix, 'conda-meta')):
            missing = deviations.missing_packages
            if len(missing) > 0:
                try:
                    # TODO we are ignoring package versions here
                    # https://github.com/Anaconda-Server/conda-kapsel/issues/77
                    conda_api.install(prefix=prefix, pkgs=list(missing), channels=spec.channels)
                except conda_api.CondaError as e:
                    raise DappledError("Failed to install missing packages: " + ", ".join(missing))
        else:
            # Create environment from scratch
            try:
                conda_api.create(prefix=prefix, pkgs=list(command_line_packages), channels=spec.channels)
            except conda_api.CondaError as e:
                raise DappledError("Failed to create environment at %s: %s" % (prefix, str(e)))

        # now add pip if needed
        missing = list(deviations.missing_pip_packages)
        if len(missing) > 0:
            try:
                pip_api.install(prefix=prefix, pkgs=missing)
            except pip_api.PipError as e:
                raise DappledError("Failed to install missing pip packages: " + ", ".join(missing))
    from conda_kapsel.internal.default_conda_manager import DefaultCondaManager
    DefaultCondaManager.fix_environment_deviations = fix_environment_deviations

    def _get_conda_command(extra_args):
        # just use whatever conda is on the path
        # cmd_list = ['conda']
        # unbuffered python output
        cmd_list = ['python', '-u', '-m', 'conda']

        cmd_list.extend(extra_args)
        # print(cmd_list)
        return cmd_list
    import conda_kapsel.internal.conda_api
    conda_kapsel.internal.conda_api._get_conda_command = _get_conda_command

    from conda_kapsel.internal.conda_api import _call_conda as _call_conda_orig
    def _call_conda(extra_args):
        from conda_kapsel.internal.conda_api import _get_conda_command, CondaError

        # only commandeer function on installing and creating
        if extra_args[0] in ('install', 'create'):
            if '--quiet' in extra_args:
                extra_args.remove('--quiet')
        else:
            return _call_conda_orig(extra_args)

        cmd_list = _get_conda_command(extra_args)

        try:
            p = subprocess.Popen(cmd_list, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        except OSError as e:
            raise CondaError("failed to run: %r: %r" % (" ".join(cmd_list), repr(e)))

        out = watch_conda_install(p)

        # TODO: parse output for error
        if p.returncode != 0:
            errstr = 'an error occurred'
            print('\n'.join(out))
            raise CondaError('%s: %s' % (" ".join(cmd_list), errstr))

        return ''.join(out)
    conda_kapsel.internal.conda_api._call_conda = _call_conda

def run_kapsel_command(*args):
    from conda_kapsel.commands.main import _parse_args_and_run_subcommand
    argv = [''] + list(args)
    _parse_args_and_run_subcommand(argv)

class KapselEnv:
    def __init__(self, dirname='.'):
        from conda_kapsel.commands.prepare_with_mode import UI_MODE_TEXT_DEVELOPMENT_DEFAULTS_OR_ASK
        from conda_kapsel.commands.prepare_with_mode import prepare_with_ui_mode_printing_errors
        from conda_kapsel.commands.project_load import load_project

        project = load_project(dirname)
        ui_mode = UI_MODE_TEXT_DEVELOPMENT_DEFAULTS_OR_ASK
        conda_environment = 'default'
        print('Preparing environment...')
        result = prepare_with_ui_mode_printing_errors(project, ui_mode=ui_mode, env_spec_name=conda_environment)
        if result.failed:
            print("failed")
            return None

        # windows only allows strings for env
        self.env = dict([str(k), str(v)] for k,v in result.environ.items())
        self.env['PYTHONUNBUFFERED'] = '1'

        self.dirname = dirname

        self._prepare()

    def _prepare(self):
        dappled_core_path = os.path.dirname(
            self.run('python', '-c', 'import dappled_core; print(dappled_core.__file__)'))
        nbextension_path = os.path.join(dappled_core_path, 'static', 'nbextension')
        self.run('jupyter', 'nbextension', 'install', nbextension_path, '--sys-prefix', '--symlink')
        self.run('jupyter', 'nbextension', 'enable', 'nbextension/nbextension', '--sys-prefix')

        self.run('jupyter', 'dashboards', 'quick-setup', '--sys-prefix', '--InstallNBExtensionApp.log_level=CRITICAL')

    def run(self, *cmd_list, **kwargs):

        # get full path of exe for windows
        exe = cmd_list[0] if os.name != 'nt' else cmd_list[0] + '.exe'
        exe_path = which(exe, pathstr=self.env['PATH'])
        cmd_list = list(cmd_list)
        cmd_list[0] = exe_path

        if kwargs.get('execvpe'):
            os.execvpe(cmd_list[0], cmd_list, self.env)

        try:
            p = subprocess.Popen(cmd_list, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, 
                cwd=self.dirname, env=self.env, bufsize=1)
        except OSError as e:
            raise Exception("failed to run: %r: %r" % (" ".join(cmd_list), repr(e)))

        out = []
        for line in unbuffered(p):

            # extra chatter from dappled-core/web.py to support ctrl-c on Windows
            if line == 'ping-%#@($': continue

            if kwargs.get('print_stdout'): print(line)
            out.append(line)
        # err = p.stderr.read()
        # # (out, err) = p.communicate()
        # errstr = err.decode().strip()
        # if p.returncode != 0:
        #     raise Exception('%s: %s' % (" ".join(cmd_list), errstr))
        # elif errstr != '' and kwargs.get('print_stderr'):
        #     for line in errstr.split("\n"):
        #         print("%s %s: %s" % (cmd_list[0], cmd_list[1], line), file=sys.stderr)

        return ''.join(out)