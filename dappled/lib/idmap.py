from __future__ import absolute_import, print_function, division, unicode_literals

from glob import glob
import os
import string

from dappled.command import DAPPLED_PATH
from dappled.lib import DAPPLED_PATH, DappledError
map_path = os.path.join(DAPPLED_PATH, 'map.txt')

def save_id_mapping(id1, id2):
    pair = ' '.join([id1, id2])
    if os.path.exists(map_path):
        for line in open(map_path):
            if pair == line.strip():
                return

    with open(map_path, 'a') as f:
        print(pair, file=f)

def get_idmap(id):
    if os.path.exists(map_path):
        for line in open(map_path):
            id1, id2 = line.strip().split()

            if id == id1:
                return id2
            elif id == id2:
                return id1

    return None


def get_id_path(id):
    if '/' in id:
        username, id1 = id.split('/', 1)

        if not id1:
            raise DappledError("Invalid ID")
        elif id1[0] in string.ascii_lowercase:
            # shortname id
            publish_id = get_idmap(id)
        else:
            publish_id = id1
    else:
        publish_id = id

    if publish_id is None:
        return None

    paths = glob(os.path.join(DAPPLED_PATH, 'nb', publish_id+'*'))
    if not paths:
        return None
    paths.sort(key=lambda x: int(x.split('.v')[1]), reverse=True)
    path = paths[0]

    return path
