import time
import math

import graphviz
import git


class Colors(object):
    def __init__(self, line_color, fill_color):
        self.line_color = line_color
        self.fill_color = fill_color


type_colors = {}
object_types = ['ref', 'tag', 'commit', 'commitsummary', 'tree', 'blob']
hue_step = 1.0 / len(object_types)
hue = 0.000
for object_type in object_types:
    line = '%1.3f %1.3f %1.3f' % (hue, 1, 1)
    fill = '%1.3f %1.3f %1.3f' % (hue, 0.1, 1)
    type_colors[object_type] = Colors(line, fill)
    hue += hue_step

# types_to_include = ('blob', 'tree', 'commit', 'commitsummary', 'ref', 'tag')
# types_to_include = ('tree', 'commit', 'ref', 'tag')
types_to_include = ('commit', 'commitsummary', 'ref', 'tag')
# types_to_include = ('blob', 'tree')

#collapse_commits = False

gv = graphviz.Digraph(format='svg')
gv.graph_attr['rankdir'] = 'RL'  # Right to left (which makes the first commit on the left)

# repo = git.Repo(r'C:\Users\24860\OneDrive\Personal\Documents\Robert\code\temprepo-jjymki0k')
repo = git.Repo(r'D:\OneDrive\Personal\Documents\Robert\code\temprepo-jjymki0k')
# repo = git.Repo(r'C:\Users\cronk\PycharmProjects\mutate')
# repo = git.Repo(r'C:\Users\24860\code\git\devtools')
# repo = git.Repo(r'C:\Users\24860\code\git\common')
# repo = git.Repo('.')

def add_commit(commit):
    gv.node(commit.hexsha,
            label=commit.hexsha[:hash_length],
            color=type_colors[commit.type].line_color,
            style='filled',
            fillcolor=type_colors[commit.type].fill_color,
            penwidth='2',
            )


def add_collapsed_commits(first_hexsha, last_hexsha, commits):
    label = '%s (%d) %s' % (last_hexsha[:hash_length],
                            commits,
                            first_hexsha[:hash_length])
    gv.node(first_hexsha,
            label=label,
            color=type_colors['commitsummary'].line_color,
            style='filled',
            fillcolor=type_colors['commitsummary'].fill_color,
            penwidth='2',
            )


def add_head(head):
    gv.node(head.path,
            label=head.path,
            color=type_colors['ref'].line_color,
            style='filled',
            fillcolor=type_colors['ref'].fill_color,
            penwidth='2',
            )


def add_sym_ref(name, parent):
    gv.node(name,
            label=name,
            color=type_colors['ref'].line_color,
            style='filled',
            fillcolor=type_colors['ref'].fill_color,
            penwidth='2',
            )


edges = {}
def add_edge(git_obj, parent):
    if type(git_obj) in (git.Head, git.TagReference, git.RemoteReference):
        if git_obj.path + parent.hexsha not in edges:
            edges[git_obj.path + parent.hexsha] = None
            gv.edge(git_obj.path, parent.hexsha, label=str(type(git_obj)))
    elif type(git_obj) in (git.Commit, git.TagObject):
        if git_obj.hexsha + parent.hexsha not in edges:
            edges[git_obj.hexsha + parent.hexsha] = None
            gv.edge(git_obj.hexsha, parent.hexsha, label='parent')
    elif type(git_obj) == str:
        gv.edge(git_obj, parent, label='ref')
    else:
        raise Exception('unknown type: %s' % type(git_obj))


all_children = {}

def boring(commit):
    parents = len(commit.parents)
    if commit in all_children:
        children = len(all_children[commit])
    else:
        children = 0
    num_refs = len([x for x in commit.repo.refs if type(x) in (git.Head, git.RemoteReference) and x.object.hexsha == commit.hexsha])
    return parents == 1 and children == 1 and num_refs == 0

# Pre-scan for children, branch points
refs = repo.refs
for git_obj in refs:
    if type(git_obj) == git.Head:
        obj = git_obj.object
    elif type(git_obj) == git.Commit:
        obj = git_obj
    elif type(git_obj) in (git.TagReference, git.RemoteReference):
        obj = git_obj.commit
    else:
        raise Exception('unknown type: %s' % type(git_obj))
    while obj.parents:
        for parent in obj.parents[1:]:
            if parent.hexsha not in [x.hexsha for x in refs if type(x) == git.Commit]:
                refs.append(parent)  # Follow these other paths later
                if parent in all_children:
                    if obj not in all_children[parent]:
                        all_children[parent] += [obj]
                else:
                    all_children[parent] = [obj]
        if obj.parents[0] in all_children:
            if obj not in all_children[obj.parents[0]]:
                all_children[obj.parents[0]] += [obj]
        else:
            all_children[obj.parents[0]] = [obj]
        obj = obj.parents[0]


# Calculate the length of the short hash based on the total number of objects
num_objects = len(all_children)
hash_length = int(math.ceil(math.log(num_objects) * math.log(math.e, 2) / 2))


# Final pass, build the graph
for git_obj in refs:
    if type(git_obj) == git.Head:
        add_head(git_obj)
        add_edge(git_obj, git_obj.object)
        obj = git_obj.object
    elif type(git_obj) == git.Commit:
        add_commit(git_obj)
        obj = git_obj
    elif type(git_obj) in (git.TagReference, git.RemoteReference):
        add_head(git_obj)
        add_edge(git_obj, git_obj.object)
        # If this is an annotated tag, commit and object don't match
        if git_obj.object != git_obj.commit:
            add_commit(git_obj.object)
            add_commit(git_obj.commit)
            add_edge(git_obj.object, git_obj.commit)
        obj = git_obj.commit
    else:
        raise Exception('unknown type: %s' % type(git_obj))

    collapsing = False
    collapsed_commits = 0
    while obj:
        if collapsing:
            if boring(obj):
                last_collapsed_commit = obj
                collapsed_commits += 1
            else:
                if collapsed_commits == 1:
                    add_commit(first_collapsed_commit)
                    add_edge(first_collapsed_commit, obj)
                else:
                    add_collapsed_commits(first_collapsed_commit.hexsha,
                                          last_collapsed_commit.hexsha,
                                          collapsed_commits)
                    add_edge(first_collapsed_commit, obj)
                    # Now add this non-boring commit
                add_commit(obj)
                if obj.parents:
                    add_edge(obj, obj.parents[0])
                    for parent in obj.parents[1:]:
                            add_edge(obj, parent)
                collapsing = False
                collapsed_commits = 0
        else:
            if boring(obj):
                collapsing = True
                first_collapsed_commit = obj
                collapsed_commits = 1
            else:
                add_commit(obj)
                if obj.parents:
                    add_edge(obj, obj.parents[0])
                    for parent in obj.parents[1:]:
                        add_edge(obj, parent)
        if obj.parents:
            obj = obj.parents[0]
        else:
            obj = None

add_sym_ref('HEAD', repo.head.ref.path)
add_edge('HEAD', repo.head.ref.path)

## Calculate the length of the short hash based on the total number of objects
#num_objects = len(objects)
#hash_length = int(math.ceil(math.log(num_objects) * math.log(math.e, 2) / 2))
#
#if collapse_commits:
#    # Trace back from each ref back to the first commit, deleting commits with single parents, etc. to just show
#    # interesting parts of the branching structure.
#    secondary_parents = []
#    processed = 0
#    total = len(heads)
#    for head in heads:
#        print('%s - Finding branch/merge points: %s (%d of %d)' % (time.ctime(), head.name, processed, total))
#        processed += 1
#        if head.name != 'HEAD':
#            commit_list = [x.hexsha for x in objects]
#            obj_index = commit_list.index(head.object.hexsha)
#            obj = objects[obj_index]
##            while obj.parents:
##                if len(obj.parents) != 1:
##                    for parent in obj.parents[1:]:
##                        if parent not in secondary_parents:
##                            secondary_parents.append(old_git.Ref('secondary_head', parent.hexsha))
##                obj = obj.parents[0].object
#
#    objects_to_delete = []
#    processed = 0
#    total = len(heads + secondary_parents)
#    for head in heads + secondary_parents:
#        print('%s - Collapsing boring commits: %s (%d of %d)' % (time.ctime(), head.name, processed, total))
#        processed += 1
#        if head.name != 'HEAD':
#            obj_index = [x.hexsha for x in objects].index(head.commit.hexsha)
#            obj = objects[obj_index]
#            collapsing = False
#            in_refs = None
#            num_children = None
#            num_parents = None
#            first_commit_id = None
#            last_obj = None
#            commits = 0
#            while obj.parents:
#                obj_index = [x.hexsha for x in objects].index(obj.hexsha)
#                obj = objects[obj_index]
#                if obj_index not in objects_to_delete and obj.type in ('commit', 'tag'):  #skips summarized and already processed commits
#                    in_refs = len([x for x in heads if x.commit.hexsha == obj.hexsha]) > 0
#                    num_children = len([x for x in objects if obj.hexsha in [y.hexsha for y in x.parents]])
#                    num_parents = len(obj.parents)
#                    if collapsing:
#                        if num_parents == 1 and num_children == 1 and not in_refs:
#                            commits += 1
#                            objects_to_delete.append(obj_index)
#                        else:
#                            if commits == 1:
#                                objects_to_delete.pop()
#                            else:
#                                objects.append(old_git.CommitSummary(first_commit_id, last_obj.hexsha, commits, last_obj.parents))
#                            collapsing = False
#                            first_commit_id = None
#                    else:
#                        if num_parents == 1 and num_children == 1 and not in_refs:
#                            collapsing = True
#                            commits = 1
#                            first_commit_id = obj.hexsha
#                            objects_to_delete.append(obj_index)
#                last_obj = obj
#                obj = obj.parents[0]
#            if collapsing:
#                if num_parents == 1 and num_children == 1 and not in_refs:
#                    commits += 1
#                    objects_to_delete.append(obj_index)
#                objects.append(old_git.CommitSummary(first_commit_id, last_obj.hexsha, commits, last_obj.parents))
#    objects_to_delete = list(set(objects_to_delete))  # Need to reverse sort so we delete from end to start so indexes don't change.
#    objects_to_delete.sort(reverse=True)  # Make unique.
#    processed = 0
#    total = len(objects_to_delete)
#    for index in objects_to_delete:
#        print('%s - Removing boring commits: %s (%d of %d)' % (time.ctime(), objects[index].hexsha, processed, total))
#        processed += 1
#        del objects[index]
#
#processed = 0
#total = len(objects)
#for git_obj in objects:
#    print('%s - Building graph: %d of %d' % (time.ctime(), processed, total))
#    processed += 1
#    if git_obj.type in types_to_include:
#        if git_obj.type == 'commitsummary':
#            label = '%s (%s) %s' % (git_obj.last_commit_id[:hash_length], git_obj.commits, git_obj.hexsha[:hash_length])
#        else:
#            label = git_obj.hexsha[:hash_length]
#        gv.node(git_obj.hexsha,
#                label=label,
#                color=type_colors[git_obj.type].line_color,
#                style='filled',
#                fillcolor=type_colors[git_obj.type].fill_color,
#                penwidth='2',
#                )
#        for parent in git_obj.parents:
#            if parent.type in types_to_include:
#                gv.edge(git_obj.hexsha, parent.hexsha, label='parent')
#        for child in git_obj.children:
#            if child.type in types_to_include:
#                gv.edge(git_obj.hexsha, child.hexsha, label='child')
#
#if 'ref' in types_to_include:
#    processed = 0
#    total = len(heads)
#    for head in heads:
#        print('%s - Processing heads: %d of %d' % (time.ctime(), processed, total))
#        processed += 1
#        gv.node(head.name, color=type_colors['ref'].line_color,
#                style='filled',
#                fillcolor=type_colors['ref'].fill_color,
#                penwidth='2')
#        gv.edge(head.name, head.object.hexsha, label='ref')

gv.render('git')
