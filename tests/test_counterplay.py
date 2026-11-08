from itertools import combinations,permutations
import random
import numpy as np
from evaluator import score_five,cards_from_str
from runtime.dense_equity import score,worlds,index
from runtime.counterplay_policy import CounterplayPolicy
from game import Game,Deal,Action

def test_dense_scores_match_reference():
    rng=random.Random(552)
    for n in (3,4,5):
        for _ in range(200):
            c=rng.sample(range(36),5+n);h=c[:5];b=c[5:]
            expected=max(score_five(x+y) for x in combinations(h,2) for y in combinations(b,3))
            assert int(score(h,b))==expected

def test_legal_joint_samples_and_draw_equity():
    h=cards_from_str('As Ks Qh Jh 9c');b=cards_from_str('Ts 8s 6d')
    opp,full,shares=worlds(h,b,16000,np.random.default_rng(88127))
    for o,f in zip(opp,full):
        assert len(set(h)|set(o)|set(f))==15
        assert list(f[:3])==b
    assert .54<float(shares.mean())<.61

def test_preflop_asset_is_suit_invariant():
    policy=CounterplayPolicy();rng=random.Random(55)
    for _ in range(30):
        h=rng.sample(range(36),5);v=policy.pre[int(index(h))]
        for p in permutations(range(4)):
            q=[(c//4)*4+p[c%4] for c in h]
            assert np.array_equal(v,policy.pre[int(index(q))])

def test_profitable_all_in_draw_is_called():
    h=tuple(sorted(cards_from_str('As Ks Qh Jh 9c')))
    o=tuple(sorted(cards_from_str('6c 7c 8c 9d Tc')))
    b=tuple(cards_from_str('Ts 8s 6d Qd Kd'))
    game=Game(Deal((h,o),b),button_seat=0,hand_index=23)
    for a in [Action.RAISE_POT,Action.RAISE_POT,Action.RAISE_POT,Action.CHECK_CALL,Action.RAISE_POT]:game.apply(a)
    obs=game.observation(0)
    assert (obs.pot,obs.to_call)==(134,26)
    assert CounterplayPolicy(samples=1024).choose_action(obs,{})==Action.CHECK_CALL
