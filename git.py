""" Provides some low-level git operations from scratch for learning purposes. """
from __future__ import print_function
import subprocess
import re


class GitObject(object):
    """
    Represents a git object.
    """
    def __init__(self, sha, name=None, links=None):
        """ Initialize this object. """
        self._sha = sha
        self._name = name
        self._links = links

    def __eq__(self, other):
        """ Test if this object is equal to other. """
        return self.sha == str(other)

    def __ne__(self, other):
        """ Test if this object is not equal to other. """
        return self.sha != str(other)

    def __str__(self):
        return self.sha

    @property
    def sha(self):
        """ Return the sha of this object. """
        return self._sha

    @property
    def name(self):
        """ Return the name of this object. """
        return self._name

    @property
    def links(self):
        """ Return the links of this object. """
        return self._links

    def add_link(self, link):
        """ Add a link to this object. """
        if self._links is None:
            self._links = []

        self._links.append(link)


class GitLink(object):
    """
    Represents a git object.
    """
    def __init__(self, sha, name=None):
        """ Initialize this link. """
        self._sha = sha
        self._name = name

    def __eq__(self, other):
        """ Test if this link is equal to other. """
        return self.sha == str(other)

    def __ne__(self, other):
        """ Test if this link is not equal to other. """
        return self.sha != str(other)

    def __str__(self):
        return self.sha

    @property
    def sha(self):
        """ Return the sha of this object. """
        return self._sha

    @property
    def name(self):
        """ Return the name of this object. """
        return self._name


class Git(object):
    """
    Represents a git repo.
    """
    def __init__(self, path_to_repo='.'):
        """
        Initializes the git repo class
        :param path_to_repo: Path to the root of the git repo in question.
        """
        self._path_to_repo = path_to_repo

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
                    gobj = GitObject(sha, name)
                    objects.append(gobj)
                else:
                    gobj = next(x for x in objects if x == sha)

                obj_type = subprocess.check_output(['git', 'cat-file', sha, '-t']).strip()
                print('type: %s' % obj_type)
                obj_content = subprocess.check_output(['git', 'cat-file', sha, '-p']).strip()
                print('content: %s' % obj_content)

                if obj_type == 'commit':
                    match = re.match(r'tree (?P<tree>[A-Fa-f0-9]{40})', obj_content)
                    print('tree: %s' % match.group('tree'))
                    gobj.add_link(GitLink(match.group('tree')))
                elif obj_type == 'tree':
                    match = re.match(r'[0-9]{6} blob (?P<blob>[A-Fa-f0-9]{40})\s+(?P<name>.*)',
                                     obj_content)
                    print('blob: %s' % match.group('blob'))
                    print('name: %s' % match.group('name'))
                    gobj.add_link(GitLink(match.group('blob'), match.group('name')))
                elif obj_type == 'blob':
                    print('I\'m just a blob.')

    @property
    def path_to_repo(self):
        """ Return the path to this repo. """
        return self._path_to_repo
