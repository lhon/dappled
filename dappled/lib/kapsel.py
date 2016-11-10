import os

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