"""Counterplay: calibrated preflop equities and response-aware action values.

No opponent identity or hidden referee state is consulted. All adaptation is
kept in the half memory supplied by the tournament server.
"""
from pathlib import Path
import math
import numpy as np
from game import Action, Street
from runtime.dense_equity import index, ranks, score, worlds, DATA

RAISES=(Action.RAISE_HALF,Action.RAISE_POT)

def sigmoid(x):
    return 1/(1+np.exp(-np.clip(x,-30,30)))

class CounterplayPolicy:
    def __init__(self, seed=42, samples=256, variant='ev', config=None):
        self.seed=seed;self.samples=samples;self.variant=variant
        self.cfg={'open':.500,'iso':.525,'strong_open':.550,'reraise':.565,
                  'range_cut':.64,'response_cut':.27,'ip_cost':.07,'oop_cost':.14,
                  'bet_buffer':.025,'call_margin':0.0}
        frozen=Path(__file__).resolve().parents[1]/'data/policy_config.json'
        if frozen.exists():
            import json
            self.cfg.update(json.loads(frozen.read_text()))
        self.cfg.update(config or {})
        ranks()
        self.pre=np.load(DATA/'preflop.npy',allow_pickle=False)
        if self.pre.shape!=(376992,3) or not np.isfinite(self.pre).all():
            raise ValueError('Missing or invalid independently generated preflop asset')

    def _state(self,memory):
        if 'cp' not in memory:
            memory['cp']={'rng':np.random.default_rng(self.seed),'hand':-1,'seen':0,
                          'aggression':[[2.,8.] for _ in range(4)],'responses':{},'pending':None}
        return memory['cp']

    @staticmethod
    def _response(m,key,fold):
        s=m['responses'].setdefault(key,[2.,4.])
        s[0]+=float(fold);s[1]+=1.

    def on_hand_end(self,result,memory):
        m=self._state(memory);p=m.get('pending')
        if p is not None and p['hand']==result.hand_index:
            self._response(m,p['key'],not result.went_to_showdown and result.winner=='me')
            m['pending']=None

    def _observe(self,obs,m):
        if obs.hand_index!=m['hand']:
            m['hand']=obs.hand_index;m['seen']=0
        history=obs.action_history
        for a in history[m['seen']:]:
            if not a.is_me:
                s=m['aggression'][int(a.street)]
                s[0]+=float(a.action in RAISES);s[1]+=1
        m['seen']=len(history)
        p=m.get('pending')
        if p is not None and p['hand']==obs.hand_index and len(history)>p['index']+1:
            a=history[p['index']+1]
            if a.is_me:raise AssertionError('Public action history does not alternate')
            self._response(m,p['key'],a.action==Action.FOLD);m['pending']=None

    @staticmethod
    def _key(street,price):
        return (int(street),int(price>.23))

    def _finish(self,obs,m,action):
        if action not in obs.legal_actions:raise AssertionError('Illegal policy action')
        if action in RAISES:
            own=obs.raise_to[action]-obs.my_bet
            call=min(obs.opp_stack,max(0,obs.raise_to[action]-obs.opp_bet))
            price=call/max(1,obs.pot+own+call)
            m['pending']={'hand':obs.hand_index,'index':len(obs.action_history),
                          'key':self._key(obs.street,price)}
        return action

    def _preflop(self,obs,m):
        q,opened,tight=map(float,self.pre[int(index(obs.hole_cards))])
        raises=[a for a in RAISES if a in obs.legal_actions]
        opp_raises=sum(a.action in RAISES and not a.is_me for a in obs.action_history)
        if not opp_raises:
            if not obs.is_button and obs.to_call==0:
                if q>self.cfg['strong_open']+.01 and raises:return raises[-1]
                if q>self.cfg['iso'] and raises:return raises[0]
                return Action.CHECK_CALL
            if q>self.cfg['strong_open'] and raises:return raises[-1]
            if q>self.cfg['open'] and raises:return raises[0]
            return Action.CHECK_CALL if q>.365 else Action.FOLD
        call=min(obs.to_call,obs.my_stack);price=call/(obs.pot+call)
        rate=m['aggression'][0][0]/m['aggression'][0][1]
        weight=np.clip((.55-rate)*1.9,.20,.85)
        eq=(1-weight)*q+weight*(opened if opp_raises==1 else tight)
        spr=min(obs.my_stack-call,obs.opp_stack)/max(1,obs.pot+call)
        margin=(.035 if obs.is_button else .075)*spr/(spr+1)
        if tight>self.cfg['reraise'] and raises:return raises[-1]
        if tight>.540 and raises and m['rng'].random()<.6:return raises[0]
        if eq>=price+margin:return Action.CHECK_CALL
        return Action.FOLD

    @staticmethod
    def _latent(opp,board):
        made=score(opp,board)
        ordered=np.sort(made)
        percentile=(np.searchsorted(ordered,made,'left')+np.searchsorted(ordered,made,'right'))/(2*len(made))
        latent=percentile.copy()
        if len(board)<5:
            for suit in range(4):
                on_board=sum(c%4==suit for c in board)
                if on_board==2:
                    suited=(opp%4)==suit
                    draw=suited.sum(axis=1)>=2
                    top=np.max(np.where(suited,opp//4,-1),axis=1)/8
                    latent=np.where(draw,np.maximum(latent,.52+.19*top),latent)
        return latent

    def _weights(self,obs,m,opp):
        w=np.ones(len(opp))
        pf_raises=sum(a.action in RAISES and not a.is_me and a.street==Street.PREFLOP for a in obs.action_history)
        if pf_raises:
            q=self.pre[index(opp),0]
            rate=m['aggression'][0][0]/m['aggression'][0][1]
            cut=.485+.025*(pf_raises>1)-.06*max(0,rate-.30)
            w*=.08+.92*sigmoid((q-cut)/.022)
        latent=self._latent(opp,obs.board)
        for street in (Street.FLOP,Street.TURN,Street.RIVER):
            if street>obs.street:break
            history=[a for a in obs.action_history if not a.is_me and a.street==street]
            if not history:continue
            aggressive=[a for a in history if a.action in RAISES]
            size={Street.FLOP:3,Street.TURN:4,Street.RIVER:5}[street]
            strength=latent if street==obs.street else self._latent(opp,obs.board[:size])
            if aggressive:
                n=len(aggressive);r,a=m['aggression'][int(street)];rate=r/a
                cut=np.clip(self.cfg['range_cut']+.12*(n>1)-.50*(rate-.25),.35,.83)
                w*=.06+.94*sigmoid((strength-cut)/.11)
            elif history[-1].action==Action.CHECK_CALL:
                # A check/call is only a weak signal; retain traps and draws.
                w*=.65+.35*(1-strength)
        return w,latent

    def _realized(self,eq,spr,button):
        discount=(self.cfg['ip_cost'] if button else self.cfg['oop_cost'])*spr/(1+spr)
        return max(0.,eq-(1-eq)*discount)

    def _postflop(self,obs,m,memory):
        bank=float(memory.get('_charged_bank_spent',0))
        n=self.samples if bank<3 else max(96,self.samples//2)
        if bank>5.5:n=64
        opp,full,shares=worlds(obs.hole_cards,obs.board,n,m['rng'])
        w,latent=self._weights(obs,m,opp);total=float(w.sum())
        equity=float(w@shares/total)
        call=min(obs.to_call,obs.my_stack)
        pot=obs.pot;after=pot+call
        spr=max(0,min(obs.my_stack-call,obs.opp_stack))/max(1,after)
        realized=self._realized(equity,spr,obs.is_button)
        call_ev=(realized-self.cfg['call_margin']*float(spr>0))*after-call
        best=Action.CHECK_CALL if not call or call_ev>=0 else Action.FOLD
        best_ev=max(0.,call_ev) if call else call_ev
        for action in RAISES:
            if action not in obs.legal_actions:continue
            own=obs.raise_to[action]-obs.my_bet
            other=min(obs.opp_stack,max(0,obs.raise_to[action]-obs.opp_bet))
            final=pot+own+other;need=other/max(1,final)
            cont=.05+.95*sigmoid((latent-(self.cfg['response_cut']+1.05*need))/.10)
            predicted_fold=1-float(w@cont/total)
            response=m['responses'].get(self._key(obs.street,need))
            if response and response[1]>=14:
                learned=response[0]/response[1]
                trust=min(.65,(response[1]-4)/60)
                desired=(1-trust)*predicted_fold+trust*learned
                odds=cont/np.maximum(1e-5,1-cont)
                shift=(1-desired)/max(desired,.01)*predicted_fold/max(1-predicted_fold,.01)
                cont=(odds*shift)/(1+odds*shift)
            cw=w*cont;continue_rate=float(cw.sum()/total)
            ceq=float(cw@shares/cw.sum())
            remaining=max(0,min(obs.my_stack-own,obs.opp_stack-other))
            ceq=self._realized(ceq,remaining/max(1,final),obs.is_button)
            ev=(1-continue_rate)*pot+continue_rate*(ceq*final-own)
            # Unmodeled reraises and later betting make tiny projected gains unreliable.
            buffer=self.cfg['bet_buffer']*pot+.25
            if obs.raises_this_street and remaining>0:buffer+=.025*final
            if ev>best_ev+buffer:
                best_ev=ev;best=action
        return best

    def choose_action(self,obs,memory):
        m=self._state(memory);self._observe(obs,m)
        if obs.to_call==0 and not any(a in obs.legal_actions for a in RAISES):
            return Action.CHECK_CALL
        action=self._preflop(obs,m) if obs.street==Street.PREFLOP else self._postflop(obs,m,memory)
        return self._finish(obs,m,action)
