""" GitPlot - The git plotter. """
import sys
import math
import logging
import argparse

import graphviz
import git

__version__ = '0.0.5'


class Colors(object):
    def __init__(self, line_color, fill_color):
        self.line_color = line_color
        self.fill_color = fill_color


type_colors = {}
object_types = ['ref', 'tag', 'commit', 'commitsummary', 'commitdetails', 'tree', 'blob']
hue_step = 1.0 / len(object_types)
hue = 0.000
for object_type in object_types:
    line = '%1.3f %1.3f %1.3f' % (hue, 1, 1)
    fill = '%1.3f %1.3f %1.3f' % (hue, 0.1, 1)
    type_colors[object_type] = Colors(line, fill)
    hue += hue_step

types_to_include = ('commit', 'commitsummary', 'commitdetails', 'ref', 'tag')
# types_to_include = ('commit', 'commitsummary', 'ref', 'tag')
# types_to_include = ('tree', 'commit', 'commitsummary', 'ref', 'tag')
# types_to_include = ('blob', 'tree', 'commit', 'commitsummary', 'ref', 'tag')

collapse_commits = False
branch_diagram = False
include_remotes = True
max_depth = 5
head_only = False

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
    if commit.type == 'commit' and 'tree' in types_to_include:
        add_tree(commit, commit.tree)
    if commit.type == 'commit' and 'commitdetails' in types_to_include:
        add_commit_details(commit)


def add_ellipsis(commit):
    gv.node(commit.hexsha,
            label='...',
            color=type_colors[commit.type].line_color,
            style='filled',
            fillcolor=type_colors[commit.type].fill_color,
            penwidth='2',
           )
    if commit.type == 'commit' and 'tree' in types_to_include:
        add_tree(commit, commit.tree)


def add_commit_details(commit):
    node_id = commit.hexsha + '-details'
    details = '\n'.join([commit.author.name,
                         commit.message[:40],
                         commit.authored_datetime.isoformat() + '...'])
    gv.node(node_id,
            label=details,
            color=type_colors['commitdetails'].line_color,
            style='filled',
            fillcolor=type_colors['commitdetails'].fill_color,
            penwidth='2',
            )
    add_edge(commit.hexsha, node_id)


def add_tree(parent, tree):
    gv.node(tree.hexsha,
            label=tree.hexsha[:hash_length],
            color=type_colors[tree.type].line_color,
            style='filled',
            fillcolor=type_colors[tree.type].fill_color,
            penwidth='2',
           )
    add_edge(parent, tree)
    if 'blob' in types_to_include:
        for blob in tree.blobs:
            add_blob(tree, blob)
    for child_tree in tree.trees:
        add_tree(tree, child_tree)


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
            label = str(type(git_obj))
            label = label.split('.')[-1][:-2]
            gv.edge(git_obj.path, parent.hexsha, label=label)
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
    elif type(git_obj) == str and type(parent) == str:
        if git_obj + parent not in edges:
            edges[git_obj + parent] = None
            if git_obj == 'HEAD':
                gv.edge(git_obj, parent, label='Head')
            else:
                gv.edge(git_obj, parent, label='details')
    else:
        raise Exception('unknown type: %s' % type(git_obj))


all_children = {}


def boring(commit):
    branch_point = commit.hexsha not in [x for x in all_children if len(all_children[x]) > 1]
    parents = len(commit.parents)
    if commit in all_children:
        children = len(all_children[commit])
    else:
        children = 0
    num_refs = len([x for x in commit.repo.refs if type(x) in (git.Head, git.RemoteReference) and x.object.hexsha == commit.hexsha])
    if branch_diagram:  # This doesn't work yet.
        return parents == 1 or not branch_point
    else:
        return parents == 1 and children == 1 and num_refs == 0

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')

logging.info('Pre-scanning the tree...')
if head_only:
    refs = [x for x in repo.refs if x.path == repo.head.ref.path]
elif include_remotes:
    refs = repo.refs
else:
    refs = [x for x in repo.refs if 'remote' not in x.path]

for git_obj in refs:
    if type(git_obj) == git.Head:
        logging.info('Scanning head %s...', git_obj.path)
        obj = git_obj.object
    elif type(git_obj) == git.Commit:
        logging.info('Scanning detected merge path from %s...', git_obj.hexsha)
        obj = git_obj
    elif type(git_obj) in (git.TagReference, git.RemoteReference):
        logging.info('Scanning reference %s...', git_obj.path)
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
hash_length = max(1, int(math.ceil(math.log(num_objects) * math.log(math.e, 2) / 2)))

logging.info('Pre-scan finished.')
logging.info('%d objects found.', num_objects)
logging.info('calculated short hash length: %d', hash_length)

# Final pass, build the graph
logging.info('Creating tree diagram...')
for git_obj in refs:
    if type(git_obj) == git.Head:
        logging.info('Processing head %s...', git_obj.path)
        add_head(git_obj)
        add_edge(git_obj, git_obj.object)
        obj = git_obj.object
    elif type(git_obj) == git.Commit:
        logging.info('Processing detected merge path from %s...', git_obj.hexsha)
        add_commit(git_obj)
        obj = git_obj
    elif type(git_obj) in (git.TagReference, git.RemoteReference):
        logging.info('Processing reference %s...', git_obj.path)
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
    depth = 0
    while obj:
        depth += 1
        if depth > max_depth:
            if collapse_commits and collapsing:
                add_collapsed_commits(first_collapsed_commit.hexsha,
                                      last_collapsed_commit.hexsha,
                                      collapsed_commits)
                add_edge(first_collapsed_commit, obj)
            add_ellipsis(obj)
            obj = None
        else:
            if collapse_commits and collapsing:
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
                if collapse_commits and boring(obj):
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

logging.info('Rendering graph...')
gv.render('git')
logging.info('Done.')


def main(arguments):
    """ Entry point for command line. """
    logging.info('gitplot %s', __version__)

    parser = argparse.ArgumentParser()
    parser.add_argument('--repo-path', help='Path to the git repo.', default='.')
    parser.add_argument('--object-types', help='Which object types to display.', nargs='+', type=str, default=['commit', 'ref', 'tag'])
    parser.add_argument('--collapse-commits', action="store_true", default=True)
    parser.add_argument('--include-remotes', action="store_true", default=False)
    args = parser.parse_args(arguments)

    logging.info('args: %s', args)
    # TODO: Convert above code to be object oriented, then make calls here to use it all.

if __name__ == "__main__":
    main(sys.argv[1:])
