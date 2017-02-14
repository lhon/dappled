import os
import urllib
import zipfile

from dappled.lib import DAPPLED_PATH, ruamel
from dappled.lib.idmap import save_id_mapping
from dappled.lib.notebook import download_notebook_data, write_notebook_data

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

