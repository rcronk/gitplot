import unittest
import subprocess


class TestGit(unittest.TestCase):
    def test_pylint(self):
        self.assertEqual(0, subprocess.call(['pylint', r'--rcfile=..\pylintrc', r'..\gitplot.py']))

    def test_pep8(self):
        self.assertEqual(0, subprocess.call(['pep8', '--ignore=E124,E501', r'..\gitplot.py']))


if __name__ == '__main__':
    unittest.main()
