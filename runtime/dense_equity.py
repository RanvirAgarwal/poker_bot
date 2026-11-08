"""Exact Omaha ranks in a dense pair/triple table; legal joint runouts."""
from functools import lru_cache
from itertools import combinations
from math import comb
from pathlib import Path
import numpy as np
from evaluator import get_table

DATA = Path(__file__).resolve().parents[1] / 'data'
CHOOSE = np.array([[comb(c, k) if c >= k else 0 for c in range(36)] for k in range(6)], dtype=np.int32)
PAIRS = np.array(list(combinations(range(5), 2)))
TRIPLES = {n:np.array(list(combinations(range(n), 3))) for n in (3,4,5)}

def index(cards):
    a = np.sort(np.asarray(cards), axis=-1)
    return CHOOSE[np.arange(1,a.shape[-1]+1),a].sum(axis=-1)

@lru_cache(1)
def ranks():
    p=DATA/'pair_triple.npy'
    if p.exists():
        t=np.load(p, mmap_mode='r', allow_pickle=False)
    else:
        hands=np.array(list(combinations(range(36),5)), dtype=np.int16)
        masks=np.bitwise_or.reduce(np.left_shift(np.uint64(1),hands.astype(np.uint64)),axis=1)
        ref=get_table()
        scores=np.fromiter((ref[int(m)] for m in masks),dtype=np.int32,count=len(hands))
        t=np.zeros((630,7140),dtype=np.int32)
        for pair in PAIRS:
            triple=[x for x in range(5) if x not in pair]
            t[index(hands[:,pair]),index(hands[:,triple])]=scores
        t.setflags(write=False)
    return t

def score(holes,boards):
    holes=np.asarray(holes);boards=np.asarray(boards)
    pi=index(holes[...,PAIRS])
    ti=index(boards[...,TRIPLES[boards.shape[-1]]])
    return ranks()[pi[..., :,None],ti[...,None,:]].max(axis=(-2,-1))

def worlds(hole,board,n,rng):
    available=np.array([x for x in range(36) if x not in set(hole)|set(board)])
    draws=available[np.argsort(rng.random((n,len(available))),axis=1)[:,:10-len(board)]]
    opp=draws[:,:5]
    complete=np.concatenate([np.broadcast_to(board,(n,len(board))),draws[:,5:]],axis=1)
    a=score(hole,complete);b=score(opp,complete)
    shares=(a>b).astype(float)+0.5*(a==b)
    return opp,complete,shares
