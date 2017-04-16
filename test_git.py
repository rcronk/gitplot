import unittest
import subprocess
import logging

import git


class TestGit(unittest.TestCase):
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

        commit = git.NewGitObject.create('18e8')
        self.assertEqual(commit.object_type, 'commit')
        self.assertEqual(len(commit.parents), 1)
        self.assertEqual(commit.parents[0].commit_id, '948549522ae6dd63c318d0d13532be8e1ffa5a4b')
        self.assertEqual(len(commit.children), 1)
        self.assertEqual(commit.children[0].commit_id, '88492f905c97437264642429d353cc34daf66112')

        objects = git.Repo(r'C:\Users\cronk\AppData\Local\Temp\temprepo-jjymki0k').get_objects()
        print(objects)
        self.assertEqual(len(objects), 7)
        self.assertEqual(objects[0].object_type, 'commit')
        self.assertEqual(objects[0].commit_id, '18e88e2827fda8c626b032eb59d4edbb8522ae72')
        self.assertEqual(len(objects[0].object_content), 216)
        self.assertEqual(len(objects[0].parents), 1)
        self.assertEqual(objects[0].parents[0].commit_id, '948549522ae6dd63c318d0d13532be8e1ffa5a4b')
        self.assertEqual(objects[1].object_type, 'commit')
        self.assertEqual(objects[1].commit_id, '948549522ae6dd63c318d0d13532be8e1ffa5a4b')
        self.assertEqual(len(objects[1].object_content), 168)
        self.assertEqual(len(objects[1].parents), 0)
        self.assertEqual(len(commit.children), 1)
        self.assertEqual(commit.children[0].commit_id, '88492f905c97437264642429d353cc34daf66112')


    def test_pylint(self):
        self.assertEqual(0, subprocess.call(['pylint', 'git.py']))


if __name__ == '__main__':
    unittest.main()
