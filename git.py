""" Provides some low-level git operations from scratch for learning purposes. """
import subprocess
import re
import os
import logging


class Ref(object):
    def __init__(self, ref_name, commit_id):
        self.ref_name = ref_name
        self.commit_id = commit_id


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
        # TODO: use the same short commit_id length as git objects below
        for sha, ref_name in found_refs:
            ref_objects.append(Ref(ref_name, sha[:4]))

        head = self.git_cmd(['git', 'symbolic-ref', 'HEAD'])
        ref_objects.append(Ref('HEAD', head))
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
    _object_types = {}
    _object_contents = {}

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

    # TODO: This path default shouldn't be here
    @staticmethod
#    def git_cmd(cmd, path_to_repo=r'C:\Users\24860\OneDrive\Personal\Documents\Robert\code\temprepo-jjymki0k'):
#    def git_cmd(cmd, path_to_repo=r'C:\Users\cronk\AppData\Local\Temp\temprepo-jjymki0k'):
    def git_cmd(cmd, path_to_repo=r'C:\Users\24860\code\git\gitplot'):
#    def git_cmd(cmd, path_to_repo=r'.'):
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
        if commit_id not in cls._object_types:
            cls._object_types[commit_id] = cls.git_cmd(['git', 'cat-file', commit_id, '-t'])
        return cls._object_types[commit_id]

    @classmethod
    def get_object_content(cls, commit_id):
        if commit_id not in cls._object_contents:
            cls._object_contents[commit_id] = cls.git_cmd(['git', 'cat-file', commit_id, '-p'])
        return cls._object_contents[commit_id]

    @property
    def parents(self):
        raise Exception('Cannot call parents on base class!')

    @property
    def children(self):
        raise Exception('Cannot call children on base class!')


class Relative(object):
    def __init__(self, git_object, name):
        self.git_object = git_object
        self.name = name


class AnnotatedTag(NewGitObject):
    object_type_text = 'tag'

    @classmethod
    def is_a(cls, commit_id):
        return cls.get_object_type(commit_id) == cls.object_type_text

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
                self._children.append(Relative(NewGitObject.create(match.group('object')), 'tag'))
            else:
                logging.debug('no object in this tag?')
        return self._children


class Commit(NewGitObject):
    object_type_text = 'commit'

    @classmethod
    def is_a(cls, commit_id):
        return cls.get_object_type(commit_id) == cls.object_type_text

    @property
    def parents(self):
        if self._parents is None:
            self._parents = []
            found_parents = re.findall(r'parent (?P<parent>[A-Fa-f0-9]{40})', self.object_content)
            if found_parents:
                for parent in found_parents:
                    logging.debug('parent: %s', parent)
                    self._parents.append(Relative(NewGitObject.create(parent), 'parent'))
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
                    self._children.append(Relative(NewGitObject.create(tree), 'tree'))
            else:
                raise Exception('ERROR: No tree in this commit.')
        return self._children


class Tree(NewGitObject):
    object_type_text = 'tree'

    @classmethod
    def is_a(cls, commit_id):
        return cls.get_object_type(commit_id) == cls.object_type_text

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
            # Find blobs
            match = re.findall(r'[0-9]{6} blob (?P<blob>[A-Fa-f0-9]{40})\s+(?P<name>.*)',
                               self.object_content)
            logging.debug('blobs/names: %s', match)
            for blob, name in match:
                self._children.append(Relative(NewGitObject.create(blob), name))
            # TODO: Maybe combine blob/tree matching since they're so similar
            # Find trees
            match = re.findall(r'[0-9]{6} tree (?P<tree>[A-Fa-f0-9]{40})\s+(?P<name>.*)',
                               self.object_content)
            logging.debug('trees/names: %s', match)
            for tree, name in match:
                self._children.append(Relative(NewGitObject.create(tree), name))
        return self._children


class Blob(NewGitObject):
    object_type_text = 'blob'

    @classmethod
    def is_a(cls, commit_id):
        return cls.get_object_type(commit_id) == cls.object_type_text

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
