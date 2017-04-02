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

    def test_pylint(self):
        self.assertEqual(0, subprocess.call(['pylint', 'git.py']))


if __name__ == '__main__':
    unittest.main()
