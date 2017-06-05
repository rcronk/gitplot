import tools

rc = tools.RepoTools()
rc.create_file('file1.txt')
rc.create_file('file2.txt')
rc.run('git add file1.txt')
rc.create_file('file3.txt')
rc.run('git add file2.txt file3.txt')
rc.run('git commit -m"Adding three files."')
rc.create_file('file4.txt')
rc.create_file('file5.txt')
rc.modify_file('file2.txt')
rc.run('git add file2.txt')
rc.modify_file('file2.txt')
rc.run('git commit -m"Changing file2.txt"')
rc.run('git add file4.txt file5.txt')
rc.create_file('file2.txt')
rc.run('git add file2.txt')
rc.run('git commit -m"Putting file2.txt back"')
rc.modify_file('file1.txt')
rc.modify_file('file2.txt')
rc.run('git add file1.txt')
rc.modify_file('file1.txt')
rc.run('git commit -m"Changing file1.txt"')
rc.run('git add file1.txt')
rc.run('git add file2.txt')
rc.run('git commit -m"Changing file2.txt"')
