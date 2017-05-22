import tools

rc = tools.RepoTools()
rc.create_file('file1.txt')
rc.create_file('file2.txt')
rc.create_file('file3.txt')
rc.run('git add file1.txt file2.txt file3.txt')
rc.run('git commit -m"Adding three files."')
rc.modify_file('file2.txt')
rc.run('git add file2.txt')
rc.run('git commit -m"Changing file2.txt"')
