""" GitPlot - The git plotter. """
try:
    from __builtin__ import str  # __builtin__ vs. builtins
except:
    from builtins import str
import sys
import os
import math
import logging
import argparse
import hashlib

import graphviz
import git

__version__ = '0.0.5'


class GitPlot(object):
    class Colors(object):
        def __init__(self, line_color, fill_color):
            self._line_color = line_color
            self._fill_color = fill_color

        @property
        def line_color(self):
            return self._line_color

        @property
        def fill_color(self):
            return self._fill_color

    def __init__(self, arguments):
        """ Entry point for command line. """
        logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')
        logging.info('gitplot %s', __version__)

        parser = argparse.ArgumentParser()
        parser.add_argument('--repo-path', help='Path to the git repo.',
#                            default=r'C:\Users\24860\OneDrive\Personal\Documents\Robert\code\temprepo-jjymki0k')
#                            default=r'D:\OneDrive\Personal\Documents\Robert\code\temprepo-jjymki0k')
#                            default=r'C:\Users\24860\code\git\devtools')
#                            default=r'C:\Users\24860\code\git\common')
#                            default=r'C:\Users\24860\Documents\hti')
#                            default=r'C:\ftl')
#                            default=r'C:\Users\cronk\PycharmProjects\mutate')
                            default=r'.')
        parser.add_argument('--verbose', help='Include trees and blobs, index, etc.', action='store_true', default=False)
        parser.add_argument('--max-commit-depth', type=int, default=10)
        parser.add_argument('--output-format', type=str, default='svg')
        parser.add_argument('--rank-direction', type=str, default='RL')
        parser.add_argument('--collapse-commits', action="store_true", default=False)
        parser.add_argument('--exclude-remotes', action="store_true", default=False)
        parser.add_argument('--head-only', action="store_true", default=False)
        parser.add_argument('--branch-diagram', action="store_true", default=False)
        parser.add_argument('--commit-details', action="store_true", default=False)
        self.args = parser.parse_args(arguments)

        logging.info('args: %s', self.args)

        # parse stuff and store in self.*

        self.gv = graphviz.Digraph(format=self.args.output_format, engine='dot')
        self.gv.graph_attr['rankdir'] = self.args.rank_direction  # Right to left (which makes the first commit appear on the far left)

        self.repo = git.Repo(self.args.repo_path)

        self.refs = []

        self.edges = {}
        self.all_children = {}
        self.all_blobs = {}

        self.type_colors = {}
        object_types = ['ref', 'tag', 'commit', 'commit_summary', 'tree', 'blob', 'changed_index_entry',
                        'changed_nonindex_entry', 'untracked_file']
        hue_step = 1.0 / len(object_types)
        hue = 0.000
        for object_type in object_types:
            line = '%1.3f %1.3f %1.3f' % (hue, 1, 1)
            fill = '%1.3f %1.3f %1.3f' % (hue, 0.1, 1)
            self.type_colors[object_type] = GitPlot.Colors(line, fill)
            hue += hue_step

        self.hash_length = 5  # Will be adjusted later

    def add_commit(self, commit):
        label = commit.hexsha[:self.hash_length]
        if commit.type == 'commit' and self.args.commit_details:
            label += '\n' + self.get_commit_details(commit)
        self.gv.node(commit.hexsha,
                label=label,
                color=self.type_colors[commit.type].line_color,
                style='filled',
                fillcolor=self.type_colors[commit.type].fill_color,
                penwidth='2',
                )
        if commit.type == 'commit' and self.args.verbose:
            self.add_tree(commit, commit.tree)

    def add_ellipsis(self, commit):
        self.gv.node(commit.hexsha,
                label='...',
                color=self.type_colors[commit.type].line_color,
                style='filled',
                fillcolor=self.type_colors[commit.type].fill_color,
                penwidth='2',
               )
        if commit.type == 'commit' and self.args.verbose:
            self.add_tree(commit, commit.tree)

    def get_commit_details(self, commit):
        if len(commit.message) > 40:
            message = commit.message[:40] + '...'
        else:
            message = commit.message
        return '\n'.join([commit.author.name,
                          message,
                          commit.authored_datetime.isoformat()])

    def add_tree(self, parent, tree):
        self.gv.node(tree.hexsha,
                label=tree.hexsha[:self.hash_length],
                color=self.type_colors[tree.type].line_color,
                style='filled',
                fillcolor=self.type_colors[tree.type].fill_color,
                penwidth='2',
               )
        self.add_edge(parent, tree)
        if self.args.verbose:
            for blob in tree.blobs:
                self.add_blob(tree, blob)
        for child_tree in tree.trees:
            self.add_tree(tree, child_tree)

    def add_blob(self, tree, blob):
        self.all_blobs[blob.hexsha] = None
        self.gv.node(blob.hexsha,
                     label=blob.hexsha[:self.hash_length],
                     color=self.type_colors[blob.type].line_color,
                     style='filled',
                     fillcolor=self.type_colors[blob.type].fill_color,
                     penwidth='2',
                     )
        self.add_edge(tree, blob)

    def add_index(self):
        self.gv.node('Index',
                     label='Index',
                     color=self.type_colors['blob'].line_color,
                     style='filled',
                     fillcolor=self.type_colors['blob'].fill_color,
                     penwidth='2',
                     )
        self.gv.node('Changed',
                     label='Changed',
                     color=self.type_colors['changed_nonindex_entry'].line_color,
                     style='filled',
                     fillcolor=self.type_colors['changed_nonindex_entry'].fill_color,
                     penwidth='2',
                     )

    def add_index_entry(self, index_entry):
        if index_entry.hexsha in self.all_blobs:
            if index_entry.path in [x.a_path for x in self.repo.index.diff(None)]:
                # This is a tracked, modified file that HAS NOT been added to the index yet.
                node_type = 'changed_nonindex_entry'
                edges = ['Changed', 'Working directory']
                label = '%s\n%s' % (index_entry.path, self.blob_hash(index_entry.path)[:self.hash_length])
            else:
                # This is a tracked, unmodified file.
                node_type = 'blob'
                edges = ['Index']
                label = '%s\n%s' % (index_entry.path, index_entry.hexsha[:self.hash_length])
        else:
            # This is a tracked, modified file that HAS been added to the index.
            node_type = 'changed_index_entry'
            edges = ['Changed', 'Index']
            label = '%s\n%s' % (index_entry.path, self.blob_hash(index_entry.path)[:self.hash_length])
        self.gv.node(label,
                     label=label,
                     color=self.type_colors[node_type].line_color,
                     style='filled',
                     fillcolor=self.type_colors[node_type].fill_color,
                     penwidth='2',
                     )
        for edge in edges:
            self.add_edge(edge, label)

    def add_untracked(self):
        self.gv.node('Working directory',
                     label='Working directory',
                     color=self.type_colors['untracked_file'].line_color,
                     style='filled',
                     fillcolor=self.type_colors['untracked_file'].fill_color,
                     penwidth='2',
                     )

    def blob_hash(self, path):
        full_path = os.path.join(self.repo.working_dir, path)
        #content = open(full_path, encoding='utf-8').read()
        content = open(full_path).read()
        blob_content = 'blob %d\0%s' % (len(content), content)
        hexsha = hashlib.sha1()
        hexsha.update(blob_content.encode('utf-8'))
        return hexsha.hexdigest()

    def add_untracked_file(self, untracked_file):
        label = '%s\n%s' % (untracked_file, self.blob_hash(untracked_file)[:self.hash_length])
        self.gv.node(label,
                label=label,
                color=self.type_colors['untracked_file'].line_color,
                style='filled',
                fillcolor=self.type_colors['untracked_file'].fill_color,
                penwidth='2',
               )
        self.add_edge('Working directory', label)

    def add_collapsed_commits(self, first_hexsha, last_hexsha, commits):
        label = '%s (%d) %s' % (last_hexsha[:self.hash_length],
                                commits,
                                first_hexsha[:self.hash_length])
        self.gv.node(first_hexsha,
                label=label,
                color=self.type_colors['commit_summary'].line_color,
                style='filled',
                fillcolor=self.type_colors['commit_summary'].fill_color,
                penwidth='2',
               )

    def add_head(self, head):
        self.gv.node(head.path,
                label=head.path,
                color=self.type_colors['ref'].line_color,
                style='filled',
                fillcolor=self.type_colors['ref'].fill_color,
                penwidth='2',
               )

    def add_sym_ref(self, name, parent):
        self.gv.node(name,
                label=name,
                color=self.type_colors['ref'].line_color,
                style='filled',
                fillcolor=self.type_colors['ref'].fill_color,
                penwidth='2',
               )

    def add_edge(self, git_obj, parent):
        if type(git_obj) in (git.Head, git.TagReference, git.RemoteReference):
            if git_obj.path + parent.hexsha not in self.edges:
                self.edges[git_obj.path + parent.hexsha] = None
                label = str(type(git_obj)).lower()
                label = label.split('.')[-1][:-2]
                self.gv.edge(git_obj.path, parent.hexsha, label=label)
        elif type(git_obj) in (git.Commit, git.TagObject) and type(parent) in (git.Commit, git.TagObject):
            if git_obj.hexsha + parent.hexsha not in self.edges:
                self.edges[git_obj.hexsha + parent.hexsha] = None
                self.gv.edge(git_obj.hexsha, parent.hexsha, label='parent')
        elif type(git_obj) in (git.Commit, git.TagObject) and type(parent) in (git.Tree, ):
            if git_obj.hexsha + parent.hexsha not in self.edges:
                self.edges[git_obj.hexsha + parent.hexsha] = None
                self.gv.edge(git_obj.hexsha, parent.hexsha, label='tree')
        elif type(git_obj) in (git.Tree, ):
            if git_obj.hexsha + parent.hexsha not in self.edges:
                self.edges[git_obj.hexsha + parent.hexsha] = None
                self.gv.edge(git_obj.hexsha, parent.hexsha, label=parent.name)
        elif type(git_obj) in (str, unicode) and type(parent) in (str, unicode):
#        elif type(git_obj) == str and type(parent) == str:
            if git_obj + parent not in self.edges:
                self.edges[git_obj + parent] = None
                if git_obj == 'HEAD':
                    self.gv.edge(git_obj, parent, label='head')
                elif git_obj == 'Index':
                    self.gv.edge(git_obj, parent, label='index')
                elif git_obj == 'Working directory':
                    self.gv.edge(git_obj, parent, label='untracked')
                elif git_obj == 'Changed':
                    self.gv.edge(git_obj, parent, label='changed')
                else:
                    raise Exception('Unknown object type: %s' % git_obj)
        else:
            raise Exception('unknown type: %s' % type(git_obj))

    def boring(self, commit):
        parents = len(commit.parents)
        num_refs = len([x for x in commit.repo.refs if type(x) in (git.Head, git.RemoteReference) and x.object.hexsha == commit.hexsha])
        if self.args.branch_diagram:  # This doesn't work yet.
            branch_points = [x.hexsha for x in self.all_children if len(self.all_children[x]) > 1]
            branch_point = commit.hexsha in branch_points
            return parents == 1 and num_refs == 0 and not branch_point
        else:
            if commit in self.all_children:
                children = len(self.all_children[commit])
            else:
                children = 0
            return parents == 1 and children == 1 and num_refs == 0

    def pre_scan(self):
        logging.info('Pre-scanning the tree...')
        if self.args.head_only:
            self.refs = [x for x in self.repo.refs if x.path == self.repo.head.ref.path]
        elif not self.args.exclude_remotes:
            self.refs = self.repo.refs
        else:
            self.refs = [x for x in self.repo.refs if 'remote' not in x.path]

        for git_obj in self.refs:
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
                    if parent.hexsha not in [x.hexsha for x in self.refs if type(x) == git.Commit]:
                        self.refs.append(parent)  # Follow these other paths later
                        if parent in self.all_children:
                            if obj not in self.all_children[parent]:
                                self.all_children[parent] += [obj]
                        else:
                            self.all_children[parent] = [obj]
                if obj.parents[0] in self.all_children:
                    if obj not in self.all_children[obj.parents[0]]:
                        self.all_children[obj.parents[0]] += [obj]
                else:
                    self.all_children[obj.parents[0]] = [obj]
                obj = obj.parents[0]


        # Calculate the length of the short hash based on the total number of objects
        num_objects = len(self.all_children)
        if num_objects:
            self.hash_length = max(5, int(math.ceil(math.log(num_objects) * math.log(math.e, 2) / 2)))

        logging.info('Pre-scan finished.')
        logging.info('%d objects found.', num_objects)
        logging.info('calculated short hash length: %d', self.hash_length)

    def draw_graph(self):
        # Final pass, build the graph
        logging.info('Creating tree diagram...')
        for git_obj in self.refs:
            if type(git_obj) == git.Head:
                logging.info('Processing head %s...', git_obj.path)
                self.add_head(git_obj)
                self.add_edge(git_obj, git_obj.object)
                obj = git_obj.object
            elif type(git_obj) == git.Commit:
                logging.info('Processing detected merge path from %s...', git_obj.hexsha)
                self.add_commit(git_obj)
                obj = git_obj
            elif type(git_obj) in (git.TagReference, git.RemoteReference):
                logging.info('Processing reference %s...', git_obj.path)
                self.add_head(git_obj)
                self.add_edge(git_obj, git_obj.object)
                # If this is an annotated tag, commit and object don't match
                if git_obj.object != git_obj.commit:
                    self.add_commit(git_obj.object)
                    self.add_commit(git_obj.commit)
                    self.add_edge(git_obj.object, git_obj.commit)
                obj = git_obj.commit
            else:
                raise Exception('unknown type: %s' % type(git_obj))

            collapsing = False
            collapsed_commits = 0
            depth = 0
            while obj:
                depth += 1
                if depth > self.args.max_commit_depth:
                    if self.args.collapse_commits and collapsing:
                        self.add_collapsed_commits(first_collapsed_commit.hexsha,
                                              last_collapsed_commit.hexsha,
                                              collapsed_commits)
                        self.add_edge(first_collapsed_commit, obj)
                    self.add_ellipsis(obj)
                    obj = None
                else:
                    if self.args.collapse_commits and collapsing:
                        if self.boring(obj):
                            last_collapsed_commit = obj
                            collapsed_commits += 1
                        else:
                            if collapsed_commits == 1:
                                self.add_commit(first_collapsed_commit)
                                self.add_edge(first_collapsed_commit, obj)
                            else:
                                self.add_collapsed_commits(first_collapsed_commit.hexsha,
                                                      last_collapsed_commit.hexsha,
                                                      collapsed_commits)
                                self.add_edge(first_collapsed_commit, obj)
                                # Now add this non-boring commit
                            self.add_commit(obj)
                            if obj.parents:
                                self.add_edge(obj, obj.parents[0])
                                for parent in obj.parents[1:]:
                                    self.add_edge(obj, parent)
                            collapsing = False
                            collapsed_commits = 0
                    else:
                        if self.args.collapse_commits and self.boring(obj):
                            collapsing = True
                            first_collapsed_commit = obj
                            collapsed_commits = 1
                        else:
                            self.add_commit(obj)
                            if obj.parents:
                                self.add_edge(obj, obj.parents[0])
                                for parent in obj.parents[1:]:
                                    self.add_edge(obj, parent)
                    if obj.parents:
                        obj = obj.parents[0]
                    else:
                        obj = None

        self.add_sym_ref('HEAD', self.repo.head.ref.path)
        self.add_edge('HEAD', self.repo.head.ref.path)

        if self.args.verbose:
            self.add_index()
            for key in self.repo.index.entries:
                self.add_index_entry(self.repo.index.entries[key])

        if len(self.repo.untracked_files):
            self.add_untracked()
            for untracked_file in self.repo.untracked_files:
                self.add_untracked_file(untracked_file)

        output_filename = os.path.basename(self.repo.working_tree_dir)
        logging.info('Rendering graph %s...' % output_filename)
        self.gv.render(filename=output_filename, view=True, cleanup=True)
        logging.info('Done.')

    def create_graph(self):
        self.pre_scan()
        self.draw_graph()


def main(arguments):
    gp = GitPlot(arguments)
    gp.create_graph()


if __name__ == "__main__":
    main(sys.argv[1:])
