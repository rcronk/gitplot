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

repo = git.Git(r'c:\users\24860\appdata\local\temp\temprepo-wcywm9')

objects = repo.get_objects()

for git_obj in git_objects:
    gv.node(git_obj.identifier, color=type_colors[git_obj.git_type])
    if git_obj.links:
        for link in git_obj.links:
            if link.identifier in [x.identifier for x in git_objects]:
                gv.edge(git_obj.identifier, link.identifier, label=link.name)
gv.render('git')
