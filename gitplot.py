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
# repo = git.Repo(r'D:\OneDrive\Personal\Documents\Robert\code\temprepo-jjymki0k')
# repo = git.Repo(r'C:\Users\cronk\PycharmProjects\mutate')
# repo = git.Repo(r'C:\Users\24860\code\git\devtools')
# repo = git.Repo(r'C:\Users\24860\code\git\common')
# repo = git.Repo(r'C:\Users\24860\Documents\hti')
# repo = git.Repo(r'C:\ftl')
repo = git.Repo('.')


def add_commit(commit):
    gv.node(commit.hexsha,
            label=commit.hexsha[:hash_length],
            color=type_colors[commit.type].line_color,
            style='filled',
            fillcolor=type_colors[commit.type].fill_color,
            penwidth='2',
            )
    if commit.type == 'commit':
        add_tree(commit)


def add_tree(commit):
    gv.node(commit.tree.hexsha,
            label=commit.tree.hexsha[:hash_length],
            color=type_colors[commit.tree.type].line_color,
            style='filled',
            fillcolor=type_colors[commit.tree.type].fill_color,
            penwidth='2',
            )
    add_edge(commit, commit.tree)
    for blob in commit.tree.blobs:
        add_blob(commit.tree, blob)


def add_blob(tree, blob):
    gv.node(blob.hexsha,
            label=blob.hexsha[:hash_length],
            color=type_colors[blob.type].line_color,
            style='filled',
            fillcolor=type_colors[blob.type].fill_color,
            penwidth='2',
            )
    add_edge(tree, blob)


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
    elif type(git_obj) in (git.Commit, git.TagObject) and type(parent) in (git.Commit, git.TagObject):
        if git_obj.hexsha + parent.hexsha not in edges:
            edges[git_obj.hexsha + parent.hexsha] = None
            gv.edge(git_obj.hexsha, parent.hexsha, label='parent')
    elif type(git_obj) in (git.Commit, git.TagObject) and type(parent) in (git.Tree, ):
        if git_obj.hexsha + parent.hexsha not in edges:
            edges[git_obj.hexsha + parent.hexsha] = None
            gv.edge(git_obj.hexsha, parent.hexsha, label='tree')
    elif type(git_obj) in (git.Tree, ):
        if git_obj.hexsha + parent.hexsha not in edges:
            edges[git_obj.hexsha + parent.hexsha] = None
            gv.edge(git_obj.hexsha, parent.hexsha, label=parent.name)
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

print ('Pre-scanning the tree...')
refs = repo.refs
for git_obj in refs:
    if type(git_obj) == git.Head:
        print('Scanning head %s...' % git_obj.path)
        obj = git_obj.object
    elif type(git_obj) == git.Commit:
        print('Scanning detected merge path from %s...' % git_obj.hexsha)
        obj = git_obj
    elif type(git_obj) in (git.TagReference, git.RemoteReference):
        print('Scanning reference %s...' % git_obj.path)
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

print ('Pre-scan finished.')
print ('%d objects found.' % num_objects)
print ('calculated short hash length: %d' % hash_length)

branch_diagram = False

# Final pass, build the graph
if branch_diagram:
    # Not done yet...
    print('Creating branch diagram...')
    for obj in all_children:
        if len(all_children[obj]) > 1:
            add_commit(obj)
            for child in all_children[obj]:
                add_commit(child)
                add_edge(obj, child)
else:
    print('Creating tree diagram...')
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

print('Rendering graph...')
gv.render('git')
print('Done.')
