from __future__ import absolute_import, print_function
import os
import subprocess
import sys
from dappled.lib.utils import unbuffered

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

    # def ProjectFile_save(self):
    #     # assume save only called once...
    #     if self.injected_env_specs:
    #         del self._yaml['env_specs']

    #     del self._yaml['commands']

    #     self.orig_save()
    # ProjectFile.orig_save = ProjectFile.save
    # ProjectFile.save = ProjectFile_save

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
        out = []
        for line in unbuffered(p):
            out.append(line)

            # show progressive install status messages properly
            if line and line[0] == '[' and line[-1] == '%':
                print('\r', line, end="")
                sys.stdout.flush()
                if line.endswith('100%'):
                    print()
            elif 'ing packages ...' in line:
                print(line)

        # TODO: parse output for error
        if p.returncode != 0:
            errstr = 'an error occurred'
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

        self.env = result.environ
        self.dirname = dirname

        self._prepare()

    def _prepare(self):
        print('Setting up jupyter extensions...')
        dappled_core_path = os.path.dirname(
            self.run('python', '-c', 'import dappled_core; print(dappled_core.__file__)'))
        nbextension_path = os.path.join(dappled_core_path, 'static', 'nbextension')
        self.run('jupyter', 'nbextension', 'install', nbextension_path, '--sys-prefix', '--symlink')
        self.run('jupyter', 'nbextension', 'enable', 'nbextension/nbextension', '--sys-prefix')

        self.run('jupyter', 'dashboards', 'quick-setup', '--sys-prefix', '--InstallNBExtensionApp.log_level=CRITICAL')

    def run(self, *cmd_list, **kwargs):
        try:
            p = subprocess.Popen(cmd_list, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, 
                cwd=self.dirname, env=self.env, bufsize=1)
        except OSError as e:
            raise Exception("failed to run: %r: %r" % (" ".join(cmd_list), repr(e)))

        out = []
        for line in unbuffered(p):
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