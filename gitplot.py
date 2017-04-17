import graphviz

import git

class Colors(object):
    def __init__(self, line_color, fill_color):
        self.line_color = line_color
        self.fill_color = fill_color

type_colors = {
    'ref': Colors('0.000 1.000 1.000', '0.000 0.100 1.000'),
    'tag': Colors('0.200 1.000 1.000', '0.200 0.100 1.000'),
    'commit': Colors('0.400 1.000 1.000', '0.400 0.100 1.000'),
    'tree': Colors('0.600 1.000 1.000', '0.600 0.100 1.000'),
    'blob': Colors('0.800 1.000 1.000', '0.800 0.100 1.000'),
}

# types_to_include = ('blob', 'tree', 'commit', 'ref', 'tag')
# types_to_include = ('tree', 'commit', 'ref')
types_to_include = ('commit', 'ref', 'tag')
# types_to_include = ('blob', 'tree')

gv = graphviz.Digraph(format='svg')

repo = git.Repo(r'C:\Users\cronk\AppData\Local\Temp\temprepo-jjymki0k')
#repo = git.Repo()

objects = repo.get_objects()

for git_obj in objects:
    if git_obj.object_type in types_to_include:
        gv.node(git_obj.short_commit_id, color=type_colors[git_obj.object_type].line_color,
                                         style='filled',
                                         fillcolor=type_colors[git_obj.object_type].fill_color,
                                         penwidth='2',
                                         )
        for parent in git_obj.parents:
            if parent.git_object.object_type in types_to_include:
                gv.edge(git_obj.short_commit_id, parent.git_object.short_commit_id, label=parent.name)
        for child in git_obj.children:
            if child.git_object.object_type in types_to_include:
                gv.edge(git_obj.short_commit_id, child.git_object.short_commit_id, label=child.name)

if 'ref' in types_to_include:
    refs = repo.get_refs()

    for ref in refs:
        gv.node(ref.ref_name, color=type_colors['ref'].line_color,
                              style='filled',
                              fillcolor=type_colors['ref'].fill_color,
                              penwidth='2')
        gv.edge(ref.ref_name, ref.commit_id, label='ref')

gv.render('git')
