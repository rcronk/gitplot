import graphviz

import git


class Colors(object):
    def __init__(self, line_color, fill_color):
        self.line_color = line_color
        self.fill_color = fill_color


type_colors = {}
subclasses = ['ref'] + [x.object_type_text for x in git.GitObject.__subclasses__()]
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
collapse_commits = False  # This isn't working yet.

gv = graphviz.Digraph(format='svg')

# repo = git.Repo(r'C:\Users\24860\OneDrive\Personal\Documents\Robert\code\temprepo-jjymki0k')
# repo = git.Repo(r'C:\Users\cronk\AppData\Local\Temp\temprepo-jjymki0k')
# repo = git.Repo(r'C:\Users\24860\code\git\devtools')
repo = git.Repo()

objects = repo.get_objects()

if collapse_commits:
    # Trace back from each ref back to the first commit, deleting commits with single parents, etc. to just show
    # interesting parts of the branching structure.
    refs = repo.get_refs()
    secondary_parents = []
    for ref in refs:
        if ref.ref_name != 'HEAD':
            commit_list = [x.commit_id for x in objects]
            obj_index = commit_list.index(ref.commit_id)
            obj = objects[obj_index]
            while obj.parents:
                if len(obj.parents) != 1:
                    for parent in obj.parents[1:]:
                        secondary_parents.append(git.Ref('secondary_head', obj.commit_id))
                obj = obj.parents[0].git_object

    for ref in refs + secondary_parents:
        if ref.ref_name != 'HEAD':
            obj_index = [x.commit_id for x in objects].index(ref.commit_id)
            obj = objects[obj_index]
            collapsing = False
            first_commit_id = None
            commits = 0
            while obj.parents:
                obj_index = [x.commit_id for x in objects].index(obj.commit_id)
                obj = objects[obj_index]
                commits += 1
                assert(obj.object_type == 'commit')
                next_obj = obj.parents[0].git_object
                in_refs = [x for x in refs if x.commit_id == obj.commit_id]
                if collapsing:
                    if len(obj.parents) == 1 and not in_refs:
                        del objects[obj_index]
                    else:
                        objects.insert(obj_index, git.CommitSummary(first_commit_id, obj.commit_id, commits, obj.parents))
                        collapsing = False
                        first_commit_id = None
                        commits = 0
                else:
                    if len(obj.parents) == 1 and not in_refs:
                        collapsing = True
                        first_commit_id = obj.commit_id
                        del objects[obj_index]
                obj = next_obj
            if collapsing:
                objects.insert(obj_index, git.CommitSummary(first_commit_id, obj.commit_id, commits, obj.parents))

for git_obj in objects:
    if git_obj.object_type in types_to_include:
        gv.node(git_obj.commit_id,
                label=git_obj.commit_id[:4],
                color=type_colors[git_obj.object_type].line_color,
                style='filled',
                fillcolor=type_colors[git_obj.object_type].fill_color,
                penwidth='2',
                )
        for parent in git_obj.parents:
            if parent.git_object.object_type in types_to_include:
                gv.edge(git_obj.commit_id, parent.git_object.commit_id, label=parent.name)
        for child in git_obj.children:
            if child.git_object.object_type in types_to_include:
                gv.edge(git_obj.commit_id, child.git_object.commit_id, label=child.name)

if 'ref' in types_to_include:
    refs = repo.get_refs()

    for ref in refs:
        gv.node(ref.ref_name, color=type_colors['ref'].line_color,
                style='filled',
                fillcolor=type_colors['ref'].fill_color,
                penwidth='2')
        gv.edge(ref.ref_name, ref.commit_id, label='ref')

gv.render('git')
