from __future__ import print_function
import subprocess
import re

class Git(object):
    def __init__(self, path_to_repo='.'):
        self.path_to_repo = path_to_repo

    def get_objects(self):
        # TODO: Use self.path_to_repo
        output = subprocess.check_output(['git', 'rev-list', '--objects', '--all'])
        git_objects = re.findall('^(?P<sha1>[A-Fa-f0-9]{40})?(?P<name>.*)$', output, re.MULTILINE)
        for sha, name in git_objects:
            if sha:
                print('-' * 80)
                print('sha: %s, name: %s' % (sha, name))
                obj_type = subprocess.check_output(['git', 'cat-file', sha, '-t']).strip()
                print('type: %s' % obj_type)
                obj_content = subprocess.check_output(['git', 'cat-file', sha, '-p']).strip()
                print('content: %s' % obj_content)

                if obj_type == 'commit':
                    match = re.match(r'tree (?P<tree>[A-Fa-f0-9]{40})', obj_content)
                    print('tree: %s' % match.group('tree'))
                elif obj_type == 'tree':
                    match = re.match(r'[0-9]{6} blob (?P<blob>[A-Fa-f0-9]{40})\s+(?P<name>.*)',
                                     obj_content)
                    print('blob: %s' % match.group('blob'))
                    print('name: %s' % match.group('name'))
                elif obj_type == 'blob':
                    print('blob content')
