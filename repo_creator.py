import subprocess
import os
import tempfile
import random
import string
import logging


class RepoCreator(object):
    def __init__(self):
        self.dir_name = tempfile.mkdtemp(prefix='temprepo-')
        print('Repo directory: %s' % self.dir_name)
        self.run(['git', 'init'])

    def run(self, cmd):
        """ Executes a command and returns the output as a stripped string. """
        old_dir = os.getcwd()
        os.chdir(self.dir_name)
        output = subprocess.check_output(cmd).decode('utf-8', errors='replace').strip()
        os.chdir(old_dir)
        return output

    @staticmethod
    def get_random_string(length=20):
        return ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(length))

    def create_file(self, name):
        with open(os.path.join(self.dir_name, name), 'w') as f:
            f.write(self.get_random_string())

    def commit_file(self, name, message='Default message.'):
        self.run(['git', 'add', name])
        self.run(['git', 'commit', '-m', message])


r = RepoCreator()
for filename in ('file1.txt', 'file2.txt'):
    r.create_file(filename)
    r.commit_file(filename)
