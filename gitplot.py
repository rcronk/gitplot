import graphviz

import git


class Colors(object):
    def __init__(self, line_color, fill_color):
        self.line_color = line_color
        self.fill_color = fill_color


type_colors = {}
subclasses = ['ref'] + [x.object_type_text for x in git.NewGitObject.__subclasses__()]
hue_step = 1.0 / len(subclasses)
hue = 0.000
for subclass in subclasses:
    line = '%1.3f %1.3f %1.3f' % (hue, 1, 1)
    fill = '%1.3f %1.3f %1.3f' % (hue, 0.1, 1)
    type_colors[subclass] = Colors(line, fill)
    hue += hue_step

# types_to_include = ('blob', 'tree', 'commit', 'ref', 'tag')
# types_to_include = ('tree', 'commit', 'ref', 'tag')
types_to_include = ('commit', 'ref', 'tag')
# types_to_include = ('blob', 'tree')

gv = graphviz.Digraph(format='svg')

# repo = git.Repo(r'C:\Users\24860\OneDrive\Personal\Documents\Robert\code\temprepo-jjymki0k')
# repo = git.Repo(r'C:\Users\cronk\AppData\Local\Temp\temprepo-jjymki0k')
repo = git.Repo(r'C:\Users\24860\code\git\devtools')
# repo = git.Repo()

objects = repo.get_objects()

for git_obj in objects:
    if git_obj.object_type in types_to_include:
        gv.node(git_obj.short_commit_id,
                color=type_colors[git_obj.object_type].line_color,
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
