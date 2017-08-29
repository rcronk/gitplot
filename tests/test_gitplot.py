import unittest
import subprocess


class TestGit(unittest.TestCase):
    def test_pylint(self):
        self.assertEqual(0, subprocess.call(['pylint', '..\gitplot.py']))


if __name__ == '__main__':
    unittest.main()
