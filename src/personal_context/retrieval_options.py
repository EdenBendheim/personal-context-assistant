"""Explicit CLI-only opt-in to bounded lexical neighbors."""
from .neighbors import NeighborSearch


def add_retrieval_options(parser):
    parser.add_argument('--neighbor-window', type=int, choices=(0, 1, 2), default=0,
                        help='0 keeps lexical defaults; 1/2 adds same-thread neighbors within 24 hours')


def retrieval_for(store, window):
    if type(window) is not int or window not in (0, 1, 2):
        raise ValueError('Choose neighbor window 0, 1 or 2')
    return store if window == 0 else NeighborSearch(store, window=window)


def description(window):
    if type(window) is not int or window not in (0, 1, 2):
        raise ValueError('Choose neighbor window 0, 1 or 2')
    return dict(backend='lexical') if window == 0 else NeighborSearch(None, window=window).describe()
