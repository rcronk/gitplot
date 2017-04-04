""" Provides some low-level git operations from scratch for learning purposes. """
import subprocess
import re
import os
import logging


class GitObject(object):
    """
    Represents a git object.
    """
    def __init__(self, sha, name='', links=None, git_type=None):
        """ Initialize this object. """
        self._sha = sha
        self._name = name
        self._links = links
        self._git_type = git_type

    def __eq__(self, other):
        """ Test if this object is equal to other. """
        return self.sha == str(other)

    def __ne__(self, other):
        """ Test if this object is not equal to other. """
        return self.sha != str(other)

    def __str__(self):
        if self.links:
            return '%s:%s:%s:%s' % (self.git_type,
                                    self.sha,
                                    self.name,
                                    str([str(x) for x in self.links]))
        else:
            return '%s:%s:%s:%s' % (self.git_type,
                                    self.sha,
                                    self.name,
                                    'no links')

    @property
    def sha(self):
        """ Return the sha of this object. """
        return self._sha

    @property
    def short_sha(self):
        """ Return the short sha of this object. """
        return self._sha[:4]

    @property
    def name(self):
        """ Return the name of this object. """
        return self._name

    @property
    def links(self):
        """ Return the links of this object. """
        return self._links

    @property
    def git_type(self):
        """ Return the type of this object. """
        return self._git_type

    @git_type.setter
    def git_type(self, value):
        """ Set the type of this object since the type isn't known at creation. """
        self._git_type = value

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
        return '%s:%s' % (self.sha, self.name)

    @property
    def sha(self):
        """ Return the sha of this object. """
        return self._sha

    @property
    def short_sha(self):
        """ Return the short sha of this link. """
        return self._sha[:4]

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

    def git_cmd(self, cmd):
        """ Executes a git command and returns the output as a stripped string. """
        old_dir = os.getcwd()
        os.chdir(self.path_to_repo)
        # TODO: utf-8 is needed on python 3, but not on python 2.  Fix this.
        #output = subprocess.check_output(cmd).decode('utf-8').strip()
        output = subprocess.check_output(cmd).strip()
        os.chdir(old_dir)
        return output

    def get_refs(self):
        """ Get all refs """
        ref_objects = []
        all_refs = self.git_cmd(['git', 'show-ref'])
        found_refs = re.findall(r'^(?P<sha1>[A-Fa-f0-9]{40})\s(?P<ref_name>.*)$',
                                all_refs, re.MULTILINE)  #pylint: disable=no-member
        for sha, ref_name in found_refs:
            ref_objects.append(GitObject(ref_name, links=[GitLink(sha, 'ref')], git_type='ref'))
        return ref_objects

    def get_objects(self):
        """
        Gets the objects in the repo.
        :return: The objects - TBD.
        """
        output = self.git_cmd(['git', 'rev-list', '--objects', '--all'])
        git_objects = re.findall('^(?P<sha1>[A-Fa-f0-9]{40})?(?P<name>.*)$',
                                 output, re.MULTILINE)  #pylint: disable=no-member
        objects = []
        for sha, name in git_objects:
            if sha:
                logging.debug('-' * 80)
                logging.debug('object: %s', sha)
                if sha not in objects:
                    gobj = GitObject(sha, name)
                    objects.append(gobj)
                else:
                    gobj = next(x for x in objects if x == sha)

                obj_type = self.git_cmd(['git', 'cat-file', sha, '-t'])
                logging.debug('type: %s', obj_type)
                gobj.git_type = obj_type
                obj_content = self.git_cmd(['git', 'cat-file', sha, '-p'])
                logging.debug('content: %s', obj_content)

                if obj_type == 'commit':
                    match = re.search(r'tree (?P<tree>[A-Fa-f0-9]{40})', obj_content)
                    if match:
                        logging.debug('tree: %s', match.group('tree'))
                        gobj.add_link(GitLink(match.group('tree'), 'tree'))
                    else:
                        logging.debug('no tree in this commit?')
                    match = re.search(r'parent (?P<parent>[A-Fa-f0-9]{40})', obj_content)
                    if match:
                        logging.debug('parent: %s', match.group('parent'))
                        gobj.add_link(GitLink(match.group('parent'), 'parent'))
                    else:
                        logging.debug('no parent in this commit - first commit in repo?')
                elif obj_type == 'tree':
                    match = re.findall(r'[0-9]{6} blob (?P<blob>[A-Fa-f0-9]{40})\s+(?P<name>.*)',
                                       obj_content)
                    logging.debug('blobs/names: %s', match)
                    for blob, name in match:
                        gobj.add_link(GitLink(blob, name))
                elif obj_type == 'blob':
                    logging.debug('I\'m just a blob.')
        refs = self.get_refs()
        return objects + refs

    @property
    def path_to_repo(self):
        """ Return the path to this repo. """
        return self._path_to_repo
