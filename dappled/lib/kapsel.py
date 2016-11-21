from __future__ import absolute_import, print_function
import os
import subprocess
import sys
from dappled.lib.utils import unbuffered

def patch():
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
        print('Preparing environment')
        result = prepare_with_ui_mode_printing_errors(project, ui_mode=ui_mode, env_spec_name=conda_environment)
        if result.failed:
            print("failed")
            return None

        self.env = result.environ
        self.dirname = dirname

        self._prepare()

    def _prepare(self):
        print('installing jupyter extensions')
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