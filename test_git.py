import unittest
import subprocess
import logging

import git


class TestGit(unittest.TestCase):
    def test_get_objects(self):
        g = git.Git()
        objects = g.get_objects()
        for git_obj in objects:
            logging.debug(git_obj)

    def test_new_git_object(self):
        # Test the object factory
        for commit_id, obj_type in (
                                ('e8ba', git.Commit),
                                ('40ef', git.Tree),
                                ('7246', git.Tag),
                                ('e2ac', git.Blob),
                                ('refs/heads/master', git.Ref),
                               ):
            self.assertEqual(type(git.NewGitObject.create(commit_id)), obj_type)


    def test_pylint(self):
        self.assertEqual(0, subprocess.call(['pylint', 'git.py']))


if __name__ == '__main__':
    unittest.main()
