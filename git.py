""" Provides some low-level git operations from scratch for learning purposes. """
import subprocess
import re
import os
import logging


# Refactor
class Repo(object):
    """
    Represents a git repo.
    """
    def __init__(self, path_to_repo='.'):
        """
        Initializes the git repo class
        :param path_to_repo: Path to the root of the git repo in question.
        """
        self._path_to_repo = path_to_repo

    @property
    def path_to_repo(self):
        """ Return the path to this repo. """
        return self._path_to_repo

    def git_cmd(self, cmd):
        """ Executes a git command and returns the output as a stripped string. """
        old_dir = os.getcwd()
        os.chdir(self.path_to_repo)
        output = subprocess.check_output(cmd).decode('utf-8', errors='replace').strip()
        os.chdir(old_dir)
        return output

    def get_refs(self):
        """ Get all refs """
        ref_objects = []
        all_refs = self.git_cmd(['git', 'show-ref'])
        found_refs = re.findall(r'^(?P<sha1>[A-Fa-f0-9]{40})\s(?P<ref_name>.*)$',
                                all_refs, re.MULTILINE)  #pylint: disable=no-member
        # TODO: git symbolic-ref HEAD
        for sha, ref_name in found_refs:
            ref_objects.append(GitObject(ref_name, links=[GitObject(sha, 'ref')], git_type='ref'))
        return ref_objects

    def get_objects(self):
        """ Get all objects """
        all_objects = self.git_cmd(['git', 'rev-list', '--objects', '--all'])
        git_objects = re.findall('^(?P<sha1>[A-Fa-f0-9]{40}) *(?P<name>.*)$',
                                 all_objects, re.MULTILINE)  #pylint: disable=no-member
        objects = []
        for sha, name in git_objects:
            objects.append(NewGitObject.create(sha))
        return objects

class NewGitObject(object):
    def __init__(self, commit_id, short_length=4):
        self._commit_id = commit_id
        self._short_length = short_length
        self._object_type = None
        self._object_content = None
        self._parents = None
        self._children = None

    @property
    def commit_id(self):
        return self._commit_id

    @property
    def short_commit_id(self):
        return self._commit_id[:self._short_length]

    @classmethod
    def create(cls, commit_id):
        for subclass in cls.__subclasses__():
            if subclass.is_a(commit_id):
                return subclass(commit_id)

        raise Exception('No subclasses found for %s' % commit_id)

    @classmethod
    def is_a(cls, commit_id):
        raise Exception('Cannot call is_a on base class!')

    @staticmethod
    def git_cmd(cmd, path_to_repo=r'C:\Users\cronk\AppData\Local\Temp\temprepo-jjymki0k'):
        """ Executes a git command and returns the output as a stripped string. """
        old_dir = os.getcwd()
        os.chdir(path_to_repo)
        output = subprocess.check_output(cmd).decode('utf-8', errors='replace').strip()
        os.chdir(old_dir)
        return output

    @property
    def object_type(self):
        if self._object_type is None:
            self._object_type = self.get_object_type(self.commit_id)
        return self._object_type

    @property
    def object_content(self):
        if self._object_content is None:
            self._object_content = self.get_object_content(self.commit_id)
        return self._object_content

    @classmethod
    def get_object_type(cls, commit_id):
        return cls.git_cmd(['git', 'cat-file', commit_id, '-t'])

    @classmethod
    def get_object_content(cls, commit_id):
        return cls.git_cmd(['git', 'cat-file', commit_id, '-p'])

    @property
    def parents(self):
        raise Exception('Cannot call parents on base class!')

    @property
    def children(self):
        raise Exception('Cannot call children on base class!')


class Commit(NewGitObject):
    @classmethod
    def is_a(cls, commit_id):
        return cls.get_object_type(commit_id) == 'commit'

    @property
    def parents(self):
        if self._parents is None:
            self._parents = []
            found_parents = re.findall(r'parent (?P<parent>[A-Fa-f0-9]{40})', self.object_content)
            if found_parents:
                for parent in found_parents:
                    logging.debug('parent: %s', parent)
                    self._parents.append(NewGitObject.create(parent))
            else:
                logging.debug('No parent in this commit - first commit in repo?')
        return self._parents

    @property
    def children(self):
        if self._children is None:
            self._children = []
            found_trees = re.findall(r'tree (?P<tree>[A-Fa-f0-9]{40})', self.object_content)
            if found_trees:
                for tree in found_trees:
                    logging.debug('tree: %s', tree)
                    self._children.append(NewGitObject.create(tree))
            else:
                raise Exception('ERROR: No tree in this commit.')
        return self._children


class Tree(NewGitObject):
    @classmethod
    def is_a(cls, commit_id):
        return cls.get_object_type(commit_id) == 'tree'

    @property
    def parents(self):
        if self._parents is None:
            # Trees don't specify parents
            self._parents = []
        return self._parents

    @property
    def children(self):
        if self._children is None:
            self._children = []
            # TODO: trees can also contain other trees, not just blobs.
            match = re.findall(r'[0-9]{6} blob (?P<blob>[A-Fa-f0-9]{40})\s+(?P<name>.*)',
                               self.object_content)
            logging.debug('blobs/names: %s', match)
            for blob, name in match:
                # TODO: we need to insert the name somehow
                self._children.append(NewGitObject.create(blob))
        return self._children


class Blob(NewGitObject):
    @classmethod
    def is_a(cls, commit_id):
        return cls.get_object_type(commit_id) == 'blob'

    @property
    def parents(self):
        if self._parents is None:
            # Blobs don't specify parents
            self._parents = []
        return self._parents

    @property
    def children(self):
        if self._children is None:
            # Blobs don't have children
            self._children = []
        return self._children


class AnnotatedTag(NewGitObject):
    @classmethod
    def is_a(cls, commit_id):
        return cls.get_object_type(commit_id) == 'tag'

    @property
    def parents(self):
        if self._parents is None:
            # Tags don't specify parents
            self._parents = []
        return self._parents

    @property
    def children(self):
        if self._children is None:
            self._children = []
            match = re.search(r'object (?P<object>[A-Fa-f0-9]{40})', self.object_content)
            if match:
                logging.debug('tag: %s', match.group('object'))
                self._children.append(NewGitObject.create(match.group('object')))
            else:
                logging.debug('no object in this tag?')
        return self._children

def get_refs(self):
    """ Get all refs """
    ref_objects = []
    all_refs = self.git_cmd(['git', 'show-ref'])
    found_refs = re.findall(r'^(?P<commit_id>[A-Fa-f0-9]{40})\s(?P<ref_name>.*)$',
                            all_refs, re.MULTILINE)  #pylint: disable=no-member
    # TODO: git symbolic-ref HEAD
    for commit_id, ref_name in found_refs:
        ref_objects.append(Ref(ref_name, links=[GitObject(sha, 'ref')], git_type='ref'))
    return ref_objects


class Ref(object):
    def __init__(self, ref_name, commit_id):
        self.ref_name = ref_name
        self.commit_id = commit_id

# Refactor


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
    def identifier(self):
        """ Return the identifier of this object. """
        if self.git_type in ('ref', 'tag'):
            return self.sha
        else:
            return self.short_sha

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


#class GitLink(object):
#    """
#    Represents a git object.
#    """
#    def __init__(self, sha, name=None):
#        """ Initialize this link. """
#        self._sha = sha
#        self._name = name
#
#    def __eq__(self, other):
#        """ Test if this link is equal to other. """
#        return self.sha == str(other)
#
#    def __ne__(self, other):
#        """ Test if this link is not equal to other. """
#        return self.sha != str(other)
#
#    def __str__(self):
#        return '%s:%s' % (self.sha, self.name)
#
#    @property
#    def sha(self):
#        """ Return the sha of this object. """
#        return self._sha
#
#    @property
#    def short_sha(self):
#        """ Return the short sha of this link. """
#        return self._sha[:4]
#
#    @property
#    def identifier(self):
#        """ Return the identifier of this object. """
#        if self.name in ('ref', 'tag'):
#            return self.sha
#        else:
#            return self.short_sha
#
#    @property
#    def name(self):
#        """ Return the name of this object. """
#        return self._name


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
        output = subprocess.check_output(cmd).decode('utf-8', errors='replace').strip()
        os.chdir(old_dir)
        return output

    def get_refs(self):
        """ Get all refs """
        ref_objects = []
        all_refs = self.git_cmd(['git', 'show-ref'])
        found_refs = re.findall(r'^(?P<sha1>[A-Fa-f0-9]{40})\s(?P<ref_name>.*)$',
                                all_refs, re.MULTILINE)  #pylint: disable=no-member
        # TODO: git symbolic-ref HEAD
        for sha, ref_name in found_refs:
            ref_objects.append(GitObject(ref_name, links=[GitObject(sha, 'ref')], git_type='ref'))
        return ref_objects

    def get_object_type(self, sha):
        return self.git_cmd(['git', 'cat-file', sha, '-t'])

    def get_object_content(self, sha):
        return self.git_cmd(['git', 'cat-file', sha, '-p'])

    def get_objects(self):
        """
        Gets the objects in the repo.
        :return: The objects - TBD.
        """
        output = self.git_cmd(['git', 'rev-list', '--objects', '--all'])
        git_objects = re.findall('^(?P<sha1>[A-Fa-f0-9]{40})\s(?P<name>.*)$',
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

                obj_type = self.get_object_type(sha)
                logging.debug('type: %s', obj_type)
                gobj.git_type = obj_type
                obj_content = self.get_object_content(sha)
                logging.debug('content: %s', obj_content)

                if obj_type == 'commit':
                    match = re.search(r'tree (?P<tree>[A-Fa-f0-9]{40})', obj_content)
                    if match:
                        logging.debug('tree: %s', match.group('tree'))
                        gobj.add_link(GitObject(match.group('tree'), 'tree', git_type='tree'))
                    else:
                        logging.debug('no tree in this commit?')
                    # TODO: A commit can have multiple parents.
                    match = re.search(r'parent (?P<parent>[A-Fa-f0-9]{40})', obj_content)
                    if match:
                        logging.debug('parent: %s', match.group('parent'))
                        gobj.add_link(GitObject(match.group('parent'), 'parent', git_type='commit'))
                    else:
                        logging.debug('no parent in this commit - first commit in repo?')
                elif obj_type == 'tree':
                    # TODO: trees can also contain other trees, not just blobs.
                    match = re.findall(r'[0-9]{6} blob (?P<blob>[A-Fa-f0-9]{40})\s+(?P<name>.*)',
                                       obj_content)
                    logging.debug('blobs/names: %s', match)
                    for blob, name in match:
                        gobj.add_link(GitObject(blob, name, git_type='blob'))
                elif obj_type == 'blob':
                    logging.debug('I\'m just a blob.')
                elif obj_type == 'tag':
                    match = re.search(r'object (?P<object>[A-Fa-f0-9]{40})', obj_content)
                    if match:
                        logging.debug('tag: %s', match.group('object'))
                        gobj.add_link(GitObject(match.group('object'), 'tag', git_type='tag'))
                    else:
                        logging.debug('no object in this tag?')

        refs = self.get_refs()
        return objects + refs

    @property
    def path_to_repo(self):
        """ Return the path to this repo. """
        return self._path_to_repo
