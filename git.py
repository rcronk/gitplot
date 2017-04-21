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
        GitObject.set_path_to_repo(path_to_repo)

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
        for sha, ref_name in found_refs:
            ref_objects.append(Ref(ref_name, sha))

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
            objects.append(GitObject.create(sha))
        return objects

    def get_commits(self):
        """ Get all objects """
        all_commits = self.git_cmd(['git', 'log', '--format=oneline', '--all'])
        git_commits = re.findall('^(?P<sha1>[A-Fa-f0-9]{40}).*$',
                                 all_commits, re.MULTILINE)  #pylint: disable=no-member
        objects = []
        for sha in git_commits:
            objects.append(Commit(sha))
        return objects

    @staticmethod
    def get_all_object_types():
        return ['ref'] + [x.object_type_text for x in GitObject.__subclasses__()]


class GitObject(object):
    _object_types = {}
    _object_contents = {}
    _path_to_repo = None

    def __init__(self, commit_id):
        self._commit_id = commit_id
        self._object_type = None
        self._object_content = None
        self._parents = None
        self._children = None

    def __str__(self):
        return self.commit_id

    @property
    def commit_id(self):
        return self._commit_id

    @classmethod
    def create(cls, commit_id):
        for subclass in cls.__subclasses__():
            if subclass.is_a(commit_id):
                return subclass(commit_id)

        raise Exception('No subclasses found for %s' % commit_id)

    @classmethod
    def set_path_to_repo(cls, path_to_repo):
        cls._path_to_repo = path_to_repo

    @classmethod
    def is_a(cls, commit_id):
        raise Exception('Cannot call is_a on base class!')

    @classmethod
    def git_cmd(cls, cmd):
        """ Executes a git command and returns the output as a stripped string. """
        old_dir = os.getcwd()
        os.chdir(cls._path_to_repo)
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


class AnnotatedTag(GitObject):
    object_type_text = 'tag'

    @classmethod
    def is_a(cls, commit_id):
        return cls.get_object_type(commit_id) == cls.object_type_text

    @property
    def parents(self):
        if self._parents is None:
            self._parents = []
            match = re.search(r'object (?P<object>[A-Fa-f0-9]{40})', self.object_content)
            if match:
                logging.debug('tag: %s', match.group('object'))
                self._parents.append(Relative(GitObject.create(match.group('object')), 'tag'))
            else:
                logging.debug('no object in this tag?')
        return self._parents

    @property
    def children(self):
        if self._children is None:
            # Annotated tags don't have children
            self._children = []
        return self._children


class Commit(GitObject):
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
                    self._parents.append(Relative(GitObject.create(parent), 'parent'))
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
                    self._children.append(Relative(GitObject.create(tree), 'tree'))
            else:
                raise Exception('ERROR: No tree in this commit.')
        return self._children


class CommitSummary(GitObject):
    object_type_text = 'commitsummary'

    def __init__(self, first_commit_id, last_commit_id, commits, parents):
        GitObject.__init__(self, first_commit_id)
        self._parents = parents
        self._commits = commits
        self._last_commit_id = last_commit_id

    def __str__(self):
        return '%s (%s) %s' % (self._commit_id, self._commits, self._last_commit_id)

    @classmethod
    def is_a(cls, commit_id):
        return False

    @property
    def commit_id(self):
        return self._commit_id

    @property
    def last_commit_id(self):
        return self._last_commit_id

    @property
    def commits(self):
        return self._commits

    @property
    def object_type(self):
        return self.object_type_text

    @property
    def parents(self):
        return self._parents

    @property
    def children(self):
        return []


class Tree(GitObject):
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
                self._children.append(Relative(GitObject.create(blob), name))
            # TODO: Maybe combine blob/tree matching since they're so similar
            # Find trees
            match = re.findall(r'[0-9]{6} tree (?P<tree>[A-Fa-f0-9]{40})\s+(?P<name>.*)',
                               self.object_content)
            logging.debug('trees/names: %s', match)
            for tree, name in match:
                self._children.append(Relative(GitObject.create(tree), name))
        return self._children


class Blob(GitObject):
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

    def __str__(self):
        return '%s:%s' % (self.ref_name, self.commit_id)
