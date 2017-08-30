import unittest
import subprocess


class TestGit(unittest.TestCase):
    def test_pylint(self):
        self.assertEqual(0, subprocess.call(['pylint', '..\gitplot.py']))

    def test_pep8(self):
        self.assertEqual(0, subprocess.call(['pep8', '..\gitplot.py']))


if __name__ == '__main__':
    unittest.main()
