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

gv = graphviz.Digraph(format='svg')

repo = git.Repo(r'C:\Users\cronk\AppData\Local\Temp\temprepo-jjymki0k')
#repo = git.Repo()

objects = repo.get_objects()

for git_obj in objects:
    gv.node(git_obj.short_commit_id, color=type_colors[git_obj.object_type])
    for parent in git_obj.parents:
        gv.edge(git_obj.short_commit_id, parent.git_object.short_commit_id, label=parent.name)
    for child in git_obj.children:
        gv.edge(git_obj.short_commit_id, child.git_object.short_commit_id, label=child.name)

refs = repo.get_refs()

for ref in refs:
    gv.node(ref.ref_name, color=type_colors['ref'])
    gv.edge(ref.ref_name, ref.commit_id, label='ref')

gv.render('git')
