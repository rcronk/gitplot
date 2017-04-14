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
#        for commit_id, obj_type in (
#                ('e8ba', git.Commit),
#                ('3af8', git.Commit),
#                ('40ef', git.Tree),
#                ('9833', git.Tree),
#                ('7246', git.AnnotatedTag),
#                ('e2ac', git.Blob),
#                ('6d09', git.Blob),
#                                   ):
#            self.assertEqual(type(git.NewGitObject.create(commit_id)), obj_type)

        commit = git.NewGitObject.create('e8ba')
        self.assertEqual(commit.object_type, 'commit')
        self.assertEqual(len(commit.parents), 1)
        self.assertEqual(commit.parents[0].commit_id, '3af89816588d95480873a4f12d63b243625fe93e')
        self.assertEqual(len(commit.children), 1)
        self.assertEqual(commit.children[0].commit_id, '40ef44cf8bc4c7277ec108625bbbb09b5e5a3b82')

        objects = git.Repo(r'c:\users\24860\appdata\local\temp\temprepo-wcywm9').get_objects()
        print(objects)
        self.assertEqual(len(objects), 7)
        self.assertEqual(objects[0].object_type, 'commit')
        self.assertEqual(len(objects[0].object_content), 242)


    def test_pylint(self):
        self.assertEqual(0, subprocess.call(['pylint', 'git.py']))


if __name__ == '__main__':
    unittest.main()
