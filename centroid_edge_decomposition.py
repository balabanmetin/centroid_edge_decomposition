# Author: Uyen Mai
# June 2017
# utils for tree decomposition

from optparse import OptionParser
from dendropy import Tree
try:
    from queue import Queue  # python 3
except ImportError:
    from Queue import Queue  # python 2
# from tree import PhylogeneticTree
import logging
import os

_DEBUG = ("SEPP_DEBUG" in os.environ) and \
    (os.environ["SEPP_DEBUG"].lower() == "true")


def get_logging_level():
    return logging.DEBUG if _DEBUG else logging.INFO


__set_loggers = set()


def get_logger(name="sepp"):
    logger = logging.getLogger(name)
    if name not in __set_loggers:
        level = get_logging_level()
        logging_formatter = logging.Formatter(
            ("[%(asctime)s] %(filename)s (line %(lineno)d):"
             " %(levelname) 8s: %(message)s"))
        logging_formatter.datefmt = '%H:%M:%S'
        logger.setLevel(level)
        ch = logging.StreamHandler()
        ch.setLevel(level)
        ch.setFormatter(logging_formatter)
        logger.addHandler(ch)
        __set_loggers.add(name)
    return logger


_LOG = get_logger(__name__)


#    def decompose_tree(self, maxSize, strategy, minSize = None, tree_map={},
#                       decomp_strategy='normal', pdistance=1, distances=None):
def decompose_by_diameter(a_tree, strategy, max_size=None, min_size=None,
                          max_diam=None):
    def __ini_record__():
        for node in a_tree.postorder_node_iter():
            __updateNode__(node)

    def __find_midpoint_edge__(t):
        u = t.seed_node.bestLCA.anchor
        uel = u.edge_length if u.edge_length else 0
        d = 0
        while (d+uel < t.seed_node.diameter/2):
            d += uel
            u = u.parent_node
            uel = u.edge_length if u.edge_length else 0
        return u.edge

    def __find_centroid_edge__(t):
        u = t.seed_node
        product = 0
        acc_nleaf = 0

        while not u.is_leaf():
            max_child = None
            max_child_nleaf = 0
            for ch in u.child_node_iter():
                if ch.nleaf > max_child_nleaf:
                    max_child_nleaf = ch.nleaf
                    max_child = ch
            acc_nleaf += (u.nleaf-max_child.nleaf)
            new_product = max_child.nleaf * acc_nleaf
            if new_product <= product:
                break
            product = new_product
            u = max_child

        return u.edge

    def __bisect__(t, e):
        # e = __find_centroid_edge__(t)

        u = e.tail_node
        v = e.head_node

        u.remove_child(v)
        t1 = Tree(seed_node=v)

        if u.num_child_nodes() == 1:
            p = u.parent_node
            v = u.child_nodes()[0]
            l_v = v.edge_length if v.edge_length else 0
            u.remove_child(v)
            # u is the seed_node; this means the tree runs out of all but one
            # side
            if p is None:
                t.seed_node = v
                return t, t1
            l_u = u.edge_length if u.edge_length else 0
            p.remove_child(u)
            p.add_child(v)
            v.edge_length = l_u + l_v
            u = p

        while u is not None:
            __updateNode__(u)
            u = u.parent_node

        return t, t1

    def __clean_up__(t):
        for node in t.postorder_node_iter():
            delattr(node, "nleaf")
            delattr(node, "anchor")
            # delattr(node,"maxheight")
            delattr(node, "maxdepth")
            delattr(node, "diameter")
            # delattr(node,"topo_diam")
            delattr(node, "bestLCA")

    def __updateNode__(node):
        if node.is_leaf():
            node.anchor = node
            # node.maxheight = 0
            node.maxdepth = 0
            node.diameter = 0
            # node.topo_diam = 0
            node.bestLCA = node
            node.nleaf = 1
            return

        # n1 = -1
        # n2 = -1
        d1 = -1
        d2 = -1
        anchor1 = None
        node.diameter = 0
        # node.topo_diam = 0
        node.bestLCA = None
        node.nleaf = 0

        for ch in node.child_node_iter():
            node.nleaf += ch.nleaf
#               n = ch.maxheight + 1
            d = ch.maxdepth + ch.edge_length if ch.edge_length else 0
#               if n > n1:
#                   n2 = n1
#                   n1 = n
#                   anchor2 = anchor1
#                   anchor1 = ch.anchor
#               elif n > n2:
#                   n2 = n
#                   anchor2 = ch.anchor
            if d > d1:
                d2 = d1
                d1 = d
                anchor1 = ch.anchor
            elif d > d2:
                d2 = d
            if ch.diameter > node.diameter:
                node.diameter = ch.diameter
                node.bestLCA = ch.bestLCA
#               node.diameter = max(ch.diameter,node.diameter)

#        node.diameter = max(d1+d2, node.diameter)
        node.maxdepth = d1
#        node.maxheight = n1
        node.anchor = anchor1
        if d1+d2 > node.diameter:
            node.diameter = d1+d2
            node.bestLCA = node

    def __get_breaking_edge__(t, edge_type):
        if t.seed_node.nleaf <= max_size and t.seed_node.diameter <= max_diam:
            return None
        if edge_type == 'midpoint':
            e = __find_midpoint_edge__(t)
        elif edge_type == 'centroid':
            e = __find_centroid_edge__(t)
        else:
            _LOG.warning(("Invalid decomposition type! Please use either "
                          "'midpoint' or 'centroid'"))
            return None

        n = e.head_node.nleaf
        if (n < min_size) or (t.seed_node.nleaf - n) < min_size:
            return None
        return e

    def __check_stop__(t):
        return ((t.seed_node.nleaf <= max_size and
                 t.seed_node.diameter <= max_diam) or
                (t.seed_node.nleaf//2 < min_size))

    def __break_by_MP_centroid__(t):
        e = __get_breaking_edge__(t, 'midpoint')
        if e is None:
            # print("Midpoint failed. Trying centroid decomposition...")
            e = __get_breaking_edge__(t, 'centroid')
        # else:
        #    print("Successfully splitted by midpoint")
        return e

    def __break(t):
        if strategy == "centroid":
            return __get_breaking_edge__(t, 'centroid')
        elif strategy == "midpoint":
            return __break_by_MP_centroid__(t)
        else:
            raise Exception("strategy not valid: %s" % strategy)

    tqueue = Queue()

    _LOG.debug("Starting brlen decomposition ...")
    __ini_record__()
    min_size = min_size if min_size else 0
    max_size = max_size if max_size else a_tree.seed_node.nleaf
    max_diam = max_diam if max_diam else a_tree.seed_node.diameter

    _LOG.debug(
        "Now breaking by %s with min %d and max %d sizes and diameter %f ..." %
        (strategy, min_size, max_size, max_diam))
    # try using midpoint
    e = __break(a_tree)

    if e is None:
        __clean_up__(a_tree)
        return [a_tree]

    treeMap = []
    tqueue.put((a_tree, e))
    while not tqueue.empty():
        t, e = tqueue.get()
        t1, t2 = __bisect__(t, e)
        e1 = __break(t1)
        if e1 is None:
            __clean_up__(t1)
            treeMap.append(t1)
        else:
            tqueue.put((t1, e1))
        e2 = __break(t2)
        if e2 is None:
            __clean_up__(t2)
            treeMap.append(t2)
        else:
            tqueue.put((t2, e2))

    return treeMap


def decompose_tree(tree, maxSize, strategy, minSize=None, tree_map={},
                       decomp_strategy='normal', pdistance=1, distances=None,
                       maxDiam=None):
        """
        This function decomposes the tree until all subtrees are smaller than
        the max size, but does not decompose below min size.
        Two possible decompositions strategies can used: "centroid" and
        "longest".
        Returns a map containing the subtrees, in an ordered fashion.
        SIDE EFFECT: deroots the tree (TODO: necessary?)
        """
        # uym2 added #
        if decomp_strategy in ["midpoint", "centroid"]:
            tl = decompose_by_diameter(
                tree, strategy=decomp_strategy, max_size=maxSize,
                max_diam=maxDiam, min_size=minSize)
            return tl


if __name__ == "__main__":
    parser = OptionParser()
    parser.add_option("-i", "--input", dest="input_fp",
                      help="path to the input newick file", metavar="FILE")
    parser.add_option("-t", "--threshold", dest="threshold", default="600",
                      help="maximum number of elements in each cluster")

    (options, args) = parser.parse_args()

    tree = Tree.get(path=options.input_fp, schema="newick")
    tl = decompose_tree(
                tree,
                float(options.threshold),
                strategy='centroid',
                minSize=float(options.threshold) / 2,
                tree_map={}, pdistance=1,
                decomp_strategy='centroid',
                distances=None,
                maxDiam=None)

    for i in tl:
        print(i)


