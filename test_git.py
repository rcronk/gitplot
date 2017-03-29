from __future__ import print_function
import unittest
import subprocess

import git


class TestGit(unittest.TestCase):
    def test_get_objects(self):
        g = git.Git()
        objects = g.get_objects()
        print(objects)

    def test_pylint(self):
        self.assertEqual(0, subprocess.call(['pylint', 'git.py']))


if __name__ == '__main__':
    unittest.main()
