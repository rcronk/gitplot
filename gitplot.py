import graphviz

import git

type_colors = {
    'ref': 'red',
    'commit': 'green',
    'tree': 'blue',
    'blob': 'black',
    'tag': 'orange',
}

types_to_include = ('blob', 'tree', 'commit', 'ref', 'tag')
# types_to_include = ('tree', 'commit', 'ref')
# types_to_include = ('commit', 'ref')
# types_to_include = ('blob', 'tree')

# git_objects = [x for x in git.Git().get_objects() if x.git_type in types_to_include]
# git_objects = [x for x in git.Git(r'c:\users\24860\appdata\local\temp\temprepo-wcywm9').get_objects()
#                if x.git_type in types_to_include]
# git_objects = [x for x in git.Git(r'c:\users\cronk\PyCharmProjects\mutate').get_objects()
#               if x.git_type in types_to_include]
# git_objects = [x for x in git.Git(r'c:\users\24860\code\git\devtools').get_objects()
#               if x.git_type in types_to_include]


gv = graphviz.Digraph(format='svg')

repo = git.Repo(r'C:\Users\cronk\AppData\Local\Temp\temprepo-jjymki0k')

objects = repo.get_objects()

for git_obj in objects:
    gv.node(git_obj.short_commit_id, color=type_colors[git_obj.object_type])
    for parent in git_obj.parents:
        gv.edge(git_obj.short_commit_id, parent.git_object.short_commit_id, label=parent.name)
    for child in git_obj.children:
        gv.edge(git_obj.short_commit_id, child.git_object.short_commit_id, label=child.name)
gv.render('git')
