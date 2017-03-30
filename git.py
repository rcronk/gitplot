""" Provides some low-level git operations from scratch for learning purposes. """
from __future__ import print_function
import subprocess
import re

class GitObject(object):
    """
    Represents a git object.
    """
    def __init__(self, sha, name=None, links=None):
        self.sha = sha
        self.name = name
        self.links = links

    def __eq__(self, other):
        return self.sha == other.sha

class Git(object):
    """
    Represents a git repo.
    """
    def __init__(self, path_to_repo='.'):
        """
        Initializes the git repo class
        :param path_to_repo: Path to the root of the git repo in question.
        """
        self.path_to_repo = path_to_repo

    def get_objects(self):
        """
        Gets the objects in the repo.
        :return: The objects - TBD.
        """
        output = subprocess.check_output(['git', 'rev-list', '--objects', '--all',
                                          self.path_to_repo]).decode('utf-8')
        git_objects = re.findall('^(?P<sha1>[A-Fa-f0-9]{40})?(?P<name>.*)$', output, re.MULTILINE)
        objects = []
        for sha, name in git_objects:
            if sha:
                if sha not in objects:
                    # TODO: Create it
                    pass
                else:
                    # TODO: Find it and add connections to it?
                    pass

                print('sha: %s, name: %s' % (sha, name))
                obj_type = subprocess.check_output(['git', 'cat-file', sha, '-t']).strip()
                print('type: %s' % obj_type)
                obj_content = subprocess.check_output(['git', 'cat-file', sha, '-p']).strip()
                print('content: %s' % obj_content)

                if obj_type == 'commit':
                    match = re.match(r'tree (?P<tree>[A-Fa-f0-9]{40})', obj_content)
                    print('tree: %s' % match.group('tree'))
                elif obj_type == 'tree':
                    match = re.match(r'[0-9]{6} blob (?P<blob>[A-Fa-f0-9]{40})\s+(?P<name>.*)',
                                     obj_content)
                    print('blob: %s' % match.group('blob'))
                    print('name: %s' % match.group('name'))
                elif obj_type == 'blob':
                    print('blob content')
