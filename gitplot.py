""" GitPlot - The git plotter. """
import sys
import os
import math
import logging
import argparse
import hashlib

import graphviz
import git

__version__ = '0.1.0'


class GitPlot(object):
    """ GitPlot main class. """

    # pylint: disable=too-many-instance-attributes

    class Colors(object):
        """ This holds the data for line and fill colors.
        Perhaps a named tuple would be better? """
        def __init__(self, line_color, fill_color):
            self._line_color = line_color
            self._fill_color = fill_color

        @property
        def line_color(self):
            """ Returns the line color. """
            return self._line_color

        @property
        def fill_color(self):
            """ Returns the fill color. """
            return self._fill_color

    def __init__(self, arguments):
        """ Entry point for command line. """
        logging.basicConfig(level=logging.INFO,
                            format='%(asctime)s %(message)s')
        logging.info('gitplot %s', __version__)

        parser = argparse.ArgumentParser()
        parser.add_argument('--repo-path', help='Path to the git repo.',
                            # default=r'C:\Users\24860\OneDrive\...\code\temprepo-jjymki0k')
                            # default=r'D:\OneDrive\Personal\Documents\...\code\temprepo-jjymki0k')
                            # default=r'C:\Users\24860\code\git\devtools')
                            # default=r'C:\Users\24860\code\git\common')
                            # default=r'C:\Users\24860\Documents\hti')
                            # default=r'C:\ftl')
                            # default=r'C:\Users\cronk\PycharmProjects\mutate')
                            default=r'.')
        parser.add_argument('--verbose', help='Include trees and blobs, etc.',
                            action='store_true', default=False)
        parser.add_argument('--max-commit-depth', type=int, default=10)
        parser.add_argument('--output-format', type=str, default='svg')
        parser.add_argument('--rank-direction', type=str, default='RL')
        parser.add_argument('--collapse-commits', action="store_true",
                            default=False)
        parser.add_argument('--exclude-remotes', action="store_true",
                            default=False)
        parser.add_argument('--head-only', action="store_true", default=False)
        parser.add_argument('--branch-diagram', action="store_true",
                            default=False)
        parser.add_argument('--commit-details', action="store_true",
                            default=False)
        self.args = parser.parse_args(arguments)

        logging.info('args: %s', self.args)

        # parse stuff and store in self.*

        self.grv = graphviz.Digraph(format=self.args.output_format,
                                    engine='dot')
        # Right to left (which makes the first commit appear on the far left)
        self.grv.graph_attr['rankdir'] = self.args.rank_direction

        self.repo = git.Repo(self.args.repo_path)

        self.refs = []

        self.edges = {}
        self.all_children = {}
        self.all_blobs = {}

        self.type_colors = {}
        object_types = ['ref', 'tag', 'commit', 'commit_summary', 'tree',
                        'blob', 'staged_changes',
                        'unstaged_changes', 'untracked_file']
        hue_step = 1.0 / len(object_types)
        hue = 0.000
        for object_type in object_types:
            line = '%1.3f %1.3f %1.3f' % (hue, 1, 1)
            fill = '%1.3f %1.3f %1.3f' % (hue, 0.1, 1)
            self.type_colors[object_type] = GitPlot.Colors(line, fill)
            hue += hue_step

        self.hash_length = 5  # Will be adjusted later

    def add_commit(self, commit):
        """ Add a commit to the tree. """
        label = commit.hexsha[:self.hash_length]
        if commit.type == 'commit' and self.args.commit_details:
            label += '\n' + self.get_commit_details(commit)
        self.grv.node(commit.hexsha,
                      label=label,
                      color=self.type_colors[commit.type].line_color,
                      style='filled',
                      fillcolor=self.type_colors[commit.type].fill_color,
                      penwidth='2',
                     )
        if commit.type == 'commit' and self.args.verbose:
            self.add_tree(commit, commit.tree)

    def add_ellipsis(self, commit):
        """ Add an ellipsis to the tree. """
        self.grv.node(commit.hexsha,
                      label='...',
                      color=self.type_colors[commit.type].line_color,
                      style='filled',
                      fillcolor=self.type_colors[commit.type].fill_color,
                      penwidth='2',
                     )
        if commit.type == 'commit' and self.args.verbose:
            self.add_tree(commit, commit.tree)

    @staticmethod
    def get_commit_details(commit):
        """ Returns the commit details for a given commit. """
        if len(commit.message) > 40:
            message = commit.message[:40] + '...'
        else:
            message = commit.message
        return '\n'.join([commit.author.name,
                          message,
                          commit.authored_datetime.isoformat()])

    def add_tree(self, parent, tree):
        """ This adds a tree (directory) to the tree. """
        self.grv.node(tree.hexsha,
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
        """ This adds a blob to the tree. """
        self.all_blobs[blob.hexsha] = None
        self.grv.node(blob.hexsha,
                      label=blob.hexsha[:self.hash_length],
                      color=self.type_colors[blob.type].line_color,
                      style='filled',
                      fillcolor=self.type_colors[blob.type].fill_color,
                      penwidth='2',
                     )
        self.add_edge(tree, blob)

    def add_index(self):
        """ This adds the index to the tree. """
        self.grv.node('Staged Changes',
                      label='Staged Changes',
                      color=self.type_colors['staged_changes'].line_color,
                      style='filled',
                      fillcolor=self.type_colors['staged_changes'].fill_color,
                      penwidth='2',
                     )
        self.grv.node('Unstaged Changes',
                      label='Unstaged Changes',
                      color=self.type_colors['unstaged_changes'].line_color,
                      style='filled',
                      fillcolor=self.type_colors['unstaged_changes'].fill_color,
                      penwidth='2',
                     )

    def add_index_entry(self, index_entry):
        """ This adds an index entry to the tree. """
        # index_matches_content_in_repo = index_entry.hexsha in self.all_blobs
        index_to_workspace_delta = [x.a_path for x in self.repo.index.diff(None)]
        try:
            index_to_repo_delta = [x.a_path for x in self.repo.index.diff(self.repo.head.commit)]
        except ValueError:
            index_to_repo_delta = []
        unstaged_change = index_entry.path in index_to_workspace_delta
        staged_change = index_entry.path in index_to_repo_delta
        #if not unstaged_change and not staged_change:
        #    if index_entry.path in [x[0] for x in self.repo.index.entries]:
        #        staged_change = True
        #    else:
        #        pass

        if unstaged_change:
            # This is a modified file whose changes have NOT been added to the index yet.
            node_type = 'unstaged_changes'
            edge = 'Unstaged Changes'
            bhash = self.blob_hash(index_entry.path)[:self.hash_length]
            label = '%s\n%s' % (index_entry.path, bhash)
            self.grv.node(label,
                          label=label,
                          color=self.type_colors[node_type].line_color,
                          style='filled',
                          fillcolor=self.type_colors[node_type].fill_color,
                          penwidth='2',
                         )
            self.add_edge(edge, label)

        if staged_change:
            # This is a modified file whose changes HAVE been added to the index
            node_type = 'staged_changes'
            edge = 'Staged Changes'
            bhash = index_entry.hexsha[:self.hash_length]
            label = '%s\n%s' % (index_entry.path, bhash)
            self.grv.node(label,
                          label=label,
                          color=self.type_colors[node_type].line_color,
                          style='filled',
                          fillcolor=self.type_colors[node_type].fill_color,
                          penwidth='2',
                         )
            self.add_edge(edge, label)

    def add_untracked(self):
        """ This adds untracked to the tree. """
        self.grv.node('Untracked',
                      label='Untracked',
                      color=self.type_colors['untracked_file'].line_color,
                      style='filled',
                      fillcolor=self.type_colors['untracked_file'].fill_color,
                      penwidth='2',
                     )

    def blob_hash(self, path):
        """ This calculates and returns the blob hash for a file. """
        full_path = os.path.join(self.repo.working_dir, path)
        # content = open(full_path, encoding='utf-8').read()
        content = open(full_path).read()
        blob_content = 'blob %d\0%s' % (len(content), content)
        hexsha = hashlib.sha1()
        hexsha.update(blob_content.encode('utf-8'))
        return hexsha.hexdigest()

    def add_untracked_file(self, untracked_file):
        """ Add an untracked file to the graph. """
        bhash = self.blob_hash(untracked_file)[:self.hash_length]
        label = '%s\n%s' % (untracked_file, bhash)
        self.grv.node(label,
                      label=label,
                      color=self.type_colors['untracked_file'].line_color,
                      style='filled',
                      fillcolor=self.type_colors['untracked_file'].fill_color,
                      penwidth='2',
                     )
        self.add_edge('Untracked', label)

    def add_collapse_commits(self, first_hexsha, last_hexsha, commits):
        """ Add a collapsed commits node to the graph. """
        label = '%s (%d) %s' % (last_hexsha[:self.hash_length],
                                commits,
                                first_hexsha[:self.hash_length])
        self.grv.node(first_hexsha,
                      label=label,
                      color=self.type_colors['commit_summary'].line_color,
                      style='filled',
                      fillcolor=self.type_colors['commit_summary'].fill_color,
                      penwidth='2',
                     )

    def add_head(self, head):
        """ Add the HEAD node to the graph. """
        if isinstance(head, str):
            name = head
        else:
            name = head.path
        self.grv.node(name,
                      label=name,
                      color=self.type_colors['ref'].line_color,
                      style='filled',
                      fillcolor=self.type_colors['ref'].fill_color,
                      penwidth='2',
                     )

    def add_edge(self, git_obj, parent):
        """ Add an edge between two nodes to the graph. """
        obj_is_reference = isinstance(git_obj, git.Reference)
        obj_is_tag_commit = isinstance(git_obj, (git.TagObject, git.Commit))
        obj_is_tree = isinstance(git_obj, git.Tree)
        obj_is_str = isinstance(git_obj, str)
        parent_is_tag_commit = isinstance(parent, (git.TagObject, git.Commit))
        parent_is_tree = isinstance(parent, git.Tree)
        parent_is_str = isinstance(parent, str)

        if obj_is_reference:
            label = str(type(git_obj)).lower()
            label = label.split('.')[-1][:-2]
            first_node = git_obj.path
            second_node = parent.hexsha
        elif obj_is_tag_commit and parent_is_tag_commit:
            label = 'parent'
            first_node = git_obj.hexsha
            second_node = parent.hexsha
        elif obj_is_tag_commit and parent_is_tree:
            label = 'tree'
            first_node = git_obj.hexsha
            second_node = parent.hexsha
        elif obj_is_tree:
            label = parent.name
            first_node = git_obj.hexsha
            second_node = parent.hexsha
        elif obj_is_str and parent_is_str:
            label = git_obj
            first_node = git_obj
            second_node = parent
        else:
            raise Exception('unknown type: %s, %s' % (type(git_obj), type(parent)))

        if first_node + second_node not in self.edges:
            self.edges[first_node + second_node] = None
            self.grv.edge(first_node, second_node, label=label)

    def boring(self, commit):
        """ This returns True when a commit isn't pointed to by any reference
        and only has one parent and one child.  It's used to determine which
        commits can be collapsed together to simplify the graph. """
        parents = len(commit.parents)
        num_refs = len([x for x in commit.repo.refs
                        if isinstance(x, git.Reference) and
                        x.object.hexsha == commit.hexsha])
        if self.args.branch_diagram:  # This doesn't work yet.
            branch_points = [x.hexsha for x in self.all_children
                             if len(self.all_children[x]) > 1]
            branch_point = commit.hexsha in branch_points
            return parents == 1 and num_refs == 0 and not branch_point
        else:
            if commit in self.all_children:
                children = len(self.all_children[commit])
            else:
                children = 0
            return parents == 1 and children == 1 and num_refs == 0

    def pre_scan(self):
        """ This scans the git objects and does some preprocessing. """
        logging.info('Pre-scanning the tree...')
        if self.args.head_only:
            self.refs = [x for x in self.repo.refs
                         if x.path == self.repo.head.ref.path]
        elif not self.args.exclude_remotes:
            self.refs = self.repo.refs
        else:
            self.refs = [x for x in self.repo.refs
                         if 'remote' not in x.path]

        for git_obj in self.refs:
            if isinstance(git_obj, git.Head):
                logging.info('Scanning head %s...', git_obj.path)
                obj = git_obj.object
            elif isinstance(git_obj, git.Commit):
                logging.info('Scanning detected merge path from %s...',
                             git_obj.hexsha)
                obj = git_obj
            elif isinstance(git_obj, git.Reference):
                logging.info('Scanning reference %s...', git_obj.path)
                obj = git_obj.commit
            else:
                raise Exception('unknown type: %s' % type(git_obj))
            while obj.parents:
                for parent in obj.parents[1:]:
                    if parent.hexsha not in [x.hexsha for x in self.refs
                                             if isinstance(x, git.Commit)]:
                        self.refs.append(parent)  # Follow these paths later
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

        # Calculate length of the short hash based on the total # of objects
        num_objects = len(self.all_children)
        if num_objects:
            self.hash_length = max(5, int(math.ceil(math.log(num_objects) *
                                                    math.log(math.e, 2) / 2)))

        logging.info('Pre-scan finished.')
        logging.info('%d objects found.', num_objects)
        logging.info('calculated short hash length: %d', self.hash_length)

    def draw_graph(self):
        """ Once pre-scanned, the graph can now be drawn. """
        # Final pass, build the graph
        logging.info('Creating tree diagram...')
        for git_obj in self.refs:
            if isinstance(git_obj, git.Head):
                logging.info('Processing head %s...', git_obj.path)
                self.add_head(git_obj)
                self.add_edge(git_obj, git_obj.object)
                obj = git_obj.object
            elif isinstance(git_obj, git.Commit):
                logging.info('Processing detected merge path from %s...',
                             git_obj.hexsha)
                self.add_commit(git_obj)
                obj = git_obj
            elif isinstance(git_obj, git.Reference):
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
            first_collapse_commit = None
            last_collapse_commit = None
            while obj:
                depth += 1
                if depth > self.args.max_commit_depth:
                    if self.args.collapse_commits and collapsing:
                        self.add_collapse_commits(first_collapse_commit.hexsha,
                                                  last_collapse_commit.hexsha,
                                                  collapsed_commits)
                        self.add_edge(first_collapse_commit, obj)
                    self.add_ellipsis(obj)
                    obj = None
                else:
                    if self.args.collapse_commits and collapsing:
                        if self.boring(obj):
                            last_collapse_commit = obj
                            collapsed_commits += 1
                        else:
                            if collapsed_commits == 1:
                                self.add_commit(first_collapse_commit)
                                self.add_edge(first_collapse_commit, obj)
                            else:
                                self.add_collapse_commits(
                                    first_collapse_commit.hexsha,
                                    last_collapse_commit.hexsha,
                                    collapsed_commits)
                                self.add_edge(first_collapse_commit, obj)
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
                            first_collapse_commit = obj
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

        self.add_head('HEAD')
        self.add_edge('HEAD', self.repo.head.ref.path)

        if self.repo.index.entries:
            self.add_index()
            for key in self.repo.index.entries:
                self.add_index_entry(self.repo.index.entries[key])

        if self.repo.untracked_files:
            self.add_untracked()
            for untracked_file in self.repo.untracked_files:
                self.add_untracked_file(untracked_file)

        output_filename = os.path.basename(self.repo.working_tree_dir) + '.dot'
        logging.info('Rendering graph %s...', output_filename)
        self.grv.render(filename=output_filename, view=True, cleanup=True)
        logging.info('Done.')

    def create_graph(self):
        """ This scans the git objects and then draws the graph. """
        self.pre_scan()
        self.draw_graph()


def main(arguments):
    """ This is the main entry point. """
    git_plot = GitPlot(arguments)
    git_plot.create_graph()


if __name__ == "__main__":
    main(sys.argv[1:])
