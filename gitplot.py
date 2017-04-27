import time
import math

import graphviz

import git


class Colors(object):
    def __init__(self, line_color, fill_color):
        self.line_color = line_color
        self.fill_color = fill_color


type_colors = {}
object_types = git.Repo.get_all_object_types()
hue_step = 1.0 / len(object_types)
hue = 0.000
for object_type in object_types:
    line = '%1.3f %1.3f %1.3f' % (hue, 1, 1)
    fill = '%1.3f %1.3f %1.3f' % (hue, 0.1, 1)
    type_colors[object_type] = Colors(line, fill)
    hue += hue_step

# types_to_include = ('blob', 'tree', 'commit', 'ref', 'tag')
# types_to_include = ('tree', 'commit', 'ref', 'tag')
types_to_include = ('commit', 'commitsummary', 'ref', 'tag')
# types_to_include = ('blob', 'tree')

collapse_commits = True  # This isn't working yet.

gv = graphviz.Digraph(format='svg')
gv.graph_attr['rankdir'] = 'RL'  # Right to left (which makes the first commit on the left)

repo = git.Repo(r'C:\Users\24860\OneDrive\Personal\Documents\Robert\code\temprepo-jjymki0k')
# repo = git.Repo(r'C:\Users\24860\code\git\devtools')
# repo = git.Repo(r'C:\Users\24860\code\git\common')
# repo = git.Repo()

if {'tree', 'blob'} & set(types_to_include):
    objects = repo.get_objects()
else:
    objects = repo.get_commits()

# Calculate the length of the short hash based on the total number of objects
num_objects = len(objects)
hash_length = int(math.ceil(math.log(num_objects) * math.log(math.e, 2) / 2))

if collapse_commits:
    # Trace back from each ref back to the first commit, deleting commits with single parents, etc. to just show
    # interesting parts of the branching structure.
    refs = repo.get_refs()
    secondary_parents = []
    processed = 0
    total = len(refs)
    for ref in refs:
        print('%s - Finding branch/merge points: %s (%d of %d)' % (time.ctime(), ref.ref_name, processed, total))
        processed += 1
        if ref.ref_name != 'HEAD':
            commit_list = [x.commit_id for x in objects]
            obj_index = commit_list.index(ref.commit_id)
            obj = objects[obj_index]
            while obj.parents:
                if len(obj.parents) != 1:
                    for parent in obj.parents[1:]:
                        if parent not in secondary_parents:
                            secondary_parents.append(git.Ref('secondary_head', parent.git_object.commit_id))
                obj = obj.parents[0].git_object

    objects_to_delete = []
    processed = 0
    total = len(refs + secondary_parents)
    for ref in refs + secondary_parents:
        print('%s - Collapsing boring commits: %s (%d of %d)' % (time.ctime(), ref.ref_name, processed, total))
        processed += 1
        if ref.ref_name != 'HEAD':
            obj_index = [x.commit_id for x in objects].index(ref.commit_id)
            obj = objects[obj_index]
            collapsing = False
            in_refs = None
            num_children = None
            num_parents = None
            first_commit_id = None
            last_obj = None
            commits = 0
            while obj.parents:
                obj_index = [x.commit_id for x in objects].index(obj.commit_id)
                obj = objects[obj_index]
                if obj_index not in objects_to_delete and obj.object_type in ('commit', 'tag'):  #skips summarized and already processed commits
                    in_refs = len([x for x in refs if x.commit_id == obj.commit_id]) > 0
                    num_children = len([x for x in objects if obj.commit_id in [y.git_object.commit_id for y in x.parents]])
                    num_parents = len(obj.parents)
                    if collapsing:
                        if num_parents == 1 and num_children == 1 and not in_refs:
                            commits += 1
                            objects_to_delete.append(obj_index)
                        else:
                            if commits == 1:
                                objects_to_delete.pop()
                            else:
                                objects.append(git.CommitSummary(first_commit_id, last_obj.commit_id, commits, last_obj.parents))
                            collapsing = False
                            first_commit_id = None
                    else:
                        if num_parents == 1 and num_children == 1 and not in_refs:
                            collapsing = True
                            commits = 1
                            first_commit_id = obj.commit_id
                            objects_to_delete.append(obj_index)
                last_obj = obj
                obj = obj.parents[0].git_object
            if collapsing:
                if num_parents == 1 and num_children == 1 and not in_refs:
                    commits += 1
                    objects_to_delete.append(obj_index)
                objects.append(git.CommitSummary(first_commit_id, last_obj.commit_id, commits, last_obj.parents))
    objects_to_delete = list(set(objects_to_delete))  # Need to reverse sort so we delete from end to start so indexes don't change.
    objects_to_delete.sort(reverse=True)  # Make unique.
    processed = 0
    total = len(objects_to_delete)
    for index in objects_to_delete:
        print('%s - Removing boring commits: %s (%d of %d)' % (time.ctime(), objects[index].commit_id, processed, total))
        processed += 1
        del objects[index]

processed = 0
total = len(objects)
for git_obj in objects:
    print('%s - Building graph: %d of %d' % (time.ctime(), processed, total))
    processed += 1
    if git_obj.object_type in types_to_include:
        if git_obj.object_type == 'commitsummary':
            label = '%s (%s) %s' % (git_obj.last_commit_id[:hash_length], git_obj.commits, git_obj.commit_id[:hash_length])
        else:
            label = git_obj.commit_id[:hash_length]
        gv.node(git_obj.commit_id,
                label=label,
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

    processed = 0
    total = len(refs)
    for ref in refs:
        print('%s - Processing refs: %d of %d' % (time.ctime(), processed, total))
        processed += 1
        gv.node(ref.ref_name, color=type_colors['ref'].line_color,
                style='filled',
                fillcolor=type_colors['ref'].fill_color,
                penwidth='2')
        gv.edge(ref.ref_name, ref.commit_id, label='ref')

gv.render('git')
