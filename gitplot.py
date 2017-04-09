import matplotlib.pyplot as plt
import networkx as nx
import pylab

import git

type_colors = {
    'ref': 0.9,
    'commit': 0.7,
    'tree': 0.5,
    'blob': 0.3,
}

G = nx.DiGraph()

#types_to_include = ('blob', 'tree', 'commit', 'ref')
#types_to_include = ('tree', 'commit', 'ref')
types_to_include = ('commit', 'ref')
#types_to_include = ('blob', 'tree')

git_objects = [x for x in git.Git().get_objects() if x.git_type in types_to_include]
#git_objects = [x for x in git.Git(r'c:\users\cronk\PyCharmProjects\mutate').get_objects()
#               if x.git_type in types_to_include]
#git_objects = [x for x in git.Git(r'c:\users\24860\code\git\devtools').get_objects()
#               if x.git_type in types_to_include]

for git_obj in git_objects:
    if git_obj.sha.startswith('ref'):
        id = git_obj.sha
    else:
        id = git_obj.short_sha
    G.add_node(id, type=git_obj.git_type)
    if git_obj.links:
        for link in git_obj.links:
            if link.sha in [x.sha for x in git_objects]:
                G.add_edge(id, link.short_sha, name=link.name)

values = [type_colors[G.node[node]['type']] for node in G.nodes()]
edge_labels = dict([((u, v,),d['name']) for u, v, d in G.edges(data=True)])

shells = []

for obj_type in types_to_include:
    shells.append([x for x in G.nodes() if G.node[x]['type'] == obj_type])

pos = nx.shell_layout(G, nlist=shells)
#pos = nx.spring_layout(G, iterations=5000)

nx.draw_networkx_edge_labels(G, pos, edge_labels=edge_labels)

node_labels = {node:node for node in G.nodes()}
nx.draw_networkx_labels(G, pos, labels=node_labels)

nx.draw(G, pos, node_color=values, node_size=1500, cmap=plt.cm.rainbow)
pylab.show()
