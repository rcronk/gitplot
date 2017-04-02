import matplotlib.pyplot as plt
import networkx as nx
import pylab

import git

type_colors = {
    'commit': 1.0,
    'tree': 0.5,
    'blob': 0.0,
}

G = nx.DiGraph()

git_objects = git.Git().get_objects()

for git_obj in git_objects:
    G.add_node(git_obj.short_sha, type=git_obj.git_type)
    if git_obj.links:
        for link in git_obj.links:
            G.add_edge(git_obj.short_sha, link.short_sha, name=link.name)

values = [type_colors[G.node[node]['type']] for node in G.nodes()]
edge_labels = dict([((u, v,),d['name']) for u, v, d in G.edges(data=True)])

shells = []

for obj_type in ['blob', 'tree', 'commit']:
    shells.append([x for x in G.nodes() if G.node[x]['type'] == obj_type])

#pos=nx.shell_layout(G, nlist=shells)
pos=nx.spring_layout(G, iterations=5000)

nx.draw_networkx_edge_labels(G, pos, edge_labels=edge_labels)

node_labels = {node:node for node in G.nodes()}
nx.draw_networkx_labels(G, pos, labels=node_labels)

nx.draw(G, pos, node_color=values, node_size=1500, cmap=plt.cm.cool)
pylab.show()
