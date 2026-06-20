import subprocess
import os
import tempfile
import random
import string


class RepoTools(object):
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
        print(subprocess.check_output('python ..\gitplot.py --repo-path="%s" --verbose' % self.dir_name))
        return output

    @staticmethod
    def get_random_string(length=20):
        return ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(length))

    def create_file(self, name):
        with open(os.path.join(self.dir_name, name), 'w') as f:
            f.write(self.get_random_string())
        print(subprocess.check_output('python ..\gitplot.py --repo-path="%s" --verbose' % self.dir_name))

    def modify_file(self, name):
        with open(os.path.join(self.dir_name, name), 'a') as f:
            f.write(self.get_random_string())
        print(subprocess.check_output('python ..\gitplot.py --repo-path="%s" --verbose' % self.dir_name))

    def commit_file(self, name, message='Default message.'):
        self.run(['git', 'add', name])
        self.run(['git', 'commit', '-m', message])

    def create_tag(self, name, commit='HEAD', tag_type='lightweight', message='Default message'):
        if tag_type == 'lightweight':
            self.run(['git', 'tag', name, commit])
        elif tag_type == 'annotated':
            self.run(['git', 'tag', '-a', name, commit, '-m', message])
        else:
            print('Invalid tag type: "%s"' % tag_type)


if __name__ == "__main__":
    r = RepoTools()
    for filename, tag_type in (('file1.txt', 'lightweight'),
                               ('file2.txt', 'annotated')):
        r.create_file(filename)
        r.commit_file(filename)
        r.create_tag('Tag-for-%s' % filename, tag_type=tag_type)
