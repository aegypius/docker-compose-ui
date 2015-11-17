"""
find docker-compose.yml files
"""

import fnmatch
import os

MAX_DEPTH=os.environ.get('MAX_DEPTH', -1)

def walklevel(some_dir, level=-1):
    some_dir = some_dir.rstrip(os.path.sep)
    assert os.path.isdir(some_dir)
    num_sep = some_dir.count(os.path.sep)
    for root, dirs, files in os.walk(some_dir):
        yield root, dirs, files
        num_sep_this = root.count(os.path.sep)
        if level != -1 and num_sep + level <= num_sep_this:
            del dirs[:]


def find_yml_files(path):
    """
    find docker-compose.yml files in path
    """
    matches = {}
    try:
        for root, _, filenames in walklevel(path, MAX_DEPTH):
            for dirs in fnmatch.filter(filenames, 'docker-compose.yml'):
                key = root.split('/')[-1]
                matches[key] = os.path.join(os.getcwd(), root)
    except AssertionError, e:
        pass
    return matches
