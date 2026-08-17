import random, itertools, collections

RANKS = list(range(2,15))  # 11=J,12=Q,13=K,14=A
SUITS = range(4)

def make_deck():
    return [(r,s) for r in RANKS for s in SUITS]

def hand_rank(cards):
    # cards: list of (rank,suit), len<=5. Evaluate best rank category.
    ranks = sorted([c[0] for c in cards], reverse=True)
    suits = [c[1] for c in cards]
    n = len(cards)
    rank_counts = collections.Counter(ranks)
    counts = sorted(rank_counts.items(), key=lambda x: (-x[1], -x[0]))
    is_flush = n==5 and len(set(suits))==1
    uniq = sorted(set(ranks), reverse=True)
    is_straight = False
    straight_high = None
    if n==5 and len(uniq)==5:
        if uniq[0]-uniq[4]==4:
            is_straight=True; straight_high=uniq[0]
        elif uniq==[14,5,4,3,2]:
            is_straight=True; straight_high=5
    if n<5:
        # partial hand (shouldn't happen at showdown but support anyway)
        cat = 0
        if counts[0][1]==4: cat=7
        elif counts[0][1]==3: cat=3
        elif counts[0][1]==2 and len(counts)>1 and counts[1][1]==2: cat=2
        elif counts[0][1]==2: cat=1
        tiebreak = tuple(r for r,c in counts) + tuple(ranks)
        return (cat, tiebreak)
    if is_straight and is_flush:
        return (8, (straight_high,))
    if counts[0][1]==4:
        kicker = max(r for r in ranks if r!=counts[0][0])
        return (7, (counts[0][0], kicker))
    if counts[0][1]==3 and counts[1][1]==2:
        return (6, (counts[0][0], counts[1][0]))
    if is_flush:
        return (5, tuple(ranks))
    if is_straight:
        return (4, (straight_high,))
    if counts[0][1]==3:
        kickers = sorted([r for r in ranks if r!=counts[0][0]], reverse=True)
        return (3, (counts[0][0],)+tuple(kickers))
    if counts[0][1]==2 and counts[1][1]==2:
        pair_ranks = sorted([counts[0][0],counts[1][0]], reverse=True)
        kicker = max(r for r in ranks if r not in pair_ranks)
        return (2, tuple(pair_ranks)+(kicker,))
    if counts[0][1]==2:
        kickers = sorted([r for r in ranks if r!=counts[0][0]], reverse=True)
        return (1, (counts[0][0],)+tuple(kickers))
    return (0, tuple(ranks))

def fit_score(card, slot_cards):
    r,s = card
    if len(slot_cards)>=5: return -999
    score = 0
    ranks_in = [c[0] for c in slot_cards]
    suits_in = [c[1] for c in slot_cards]
    rc = collections.Counter(ranks_in)
    sc = collections.Counter(suits_in)
    score += rc.get(r,0)*12         # pairs/trips/quads building
    score += sc.get(s,0)*4          # flush building
    if slot_cards:
        mind = min(abs(r-x) for x in ranks_in)
        if mind<=4: score += max(0,5-mind)*1.5   # straight proximity
    score += r*0.05                 # mild high-card preference
    return score

class Bot:
    name="base"
    def act(self, hand, own_table, opp_table, burned):
        raise NotImplementedError

class RandomBot(Bot):
    name="random"
    def act(self, hand, own_table, opp_table, burned):
        open_slots = [i for i in range(4) if len(own_table[i])<5]
        if not burned and (not open_slots or random.random()<0.05):
            c = random.choice(hand)
            return ('burn', c)
        c = random.choice(hand)
        s = random.choice(open_slots)
        return ('play', c, s)

class GreedyBot(Bot):
    name="greedy"
    burn_threshold = 3.0
    def act(self, hand, own_table, opp_table, burned):
        open_slots = [i for i in range(4) if len(own_table[i])<5]
        if not open_slots:
            return ('burn', random.choice(hand))
        best = {}
        for c in hand:
            scores = [(fit_score(c, own_table[i]), i) for i in open_slots]
            scores.sort(reverse=True)
            best[c] = scores[0]
        worst_card = min(hand, key=lambda c: best[c][0])
        worst_val, worst_slot = best[worst_card]
        if not burned and worst_val < self.burn_threshold:
            return ('burn', worst_card)
        return ('play', worst_card, worst_slot)

class Focus3Bot(Bot):
    # Deliberately punts one column (index 3) early: dumps lowest-value cards
    # there to close it fast, concentrates rest on cols 0-2 + hidden hand.
    name="focus3"
    punt_col = 3
    burn_threshold = 3.0
    def act(self, hand, own_table, opp_table, burned):
        open_slots = [i for i in range(4) if len(own_table[i])<5]
        if not open_slots:
            return ('burn', random.choice(hand))
        # if punt column still open, dump our lowest-ranked card there
        if self.punt_col in open_slots:
            worst = min(hand, key=lambda c: c[0])
            return ('play', worst, self.punt_col)
        best = {}
        for c in hand:
            scores = [(fit_score(c, own_table[i]), i) for i in open_slots]
            scores.sort(reverse=True)
            best[c] = scores[0]
        worst_card = min(hand, key=lambda c: best[c][0])
        worst_val, worst_slot = best[worst_card]
        if not burned and worst_val < self.burn_threshold:
            return ('burn', worst_card)
        return ('play', worst_card, worst_slot)

def play_game(botA, botB, verbose=False):
    deck = make_deck()
    random.shuffle(deck)
    handA = [deck.pop() for _ in range(5)]
    handB = [deck.pop() for _ in range(5)]
    tableA = [[],[],[],[]]
    tableB = [[],[],[],[]]
    burnedA = False
    burnedB = False
    turn = 0
    players = [('A',botA), ('B',botB)]
    while deck:
        who, bot = players[turn%2]
        if who=='A':
            action = bot.act(handA, tableA, tableB, burnedA)
            if action[0]=='burn':
                c = action[1]; handA.remove(c); burnedA=True
            else:
                _, c, s = action; handA.remove(c); tableA[s].append(c)
            handA.append(deck.pop())
        else:
            action = bot.act(handB, tableB, tableA, burnedB)
            if action[0]=='burn':
                c = action[1]; handB.remove(c); burnedB=True
            else:
                _, c, s = action; handB.remove(c); tableB[s].append(c)
            handB.append(deck.pop())
        turn+=1
    # showdown
    winsA=0; winsB=0
    for i in range(4):
        ra = hand_rank(tableA[i]); rb = hand_rank(tableB[i])
        if ra>rb: winsA+=1
        elif rb>ra: winsB+=1
    ra = hand_rank(handA); rb = hand_rank(handB)
    if ra>rb: winsA+=1
    elif rb>ra: winsB+=1
    return winsA, winsB

def tournament(botA_cls, botB_cls, n=3000):
    aw=bw=tie=0
    for _ in range(n):
        wa,wb = play_game(botA_cls(), botB_cls())
        if wa>wb: aw+=1
        elif wb>wa: bw+=1
        else: tie+=1
    return aw,bw,tie

random.seed(42)
print("Random vs Random:", tournament(RandomBot, RandomBot, 3000))
print("Greedy vs Random:", tournament(GreedyBot, RandomBot, 3000))
print("Greedy vs Greedy:", tournament(GreedyBot, GreedyBot, 3000))
print("Focus3 vs Greedy:", tournament(Focus3Bot, GreedyBot, 3000))
print("Focus3 vs Random:", tournament(Focus3Bot, RandomBot, 3000))

class BuildBot(Bot):
    # Plays the card with the BEST fit to an open slot (actively builds
    # synergy in table columns) rather than hoarding good cards in hand.
    name="build"
    burn_threshold = 1.5
    def act(self, hand, own_table, opp_table, burned):
        open_slots = [i for i in range(4) if len(own_table[i])<5]
        if not open_slots:
            return ('burn', random.choice(hand))
        best = {}
        for c in hand:
            scores = [(fit_score(c, own_table[i]), i) for i in open_slots]
            scores.sort(reverse=True)
            best[c] = scores[0]
        best_card = max(hand, key=lambda c: best[c][0])
        val, slot = best[best_card]
        # if even our best option is a dead card, consider burning the worst one instead
        worst_card = min(hand, key=lambda c: best[c][0])
        if not burned and best[worst_card][0] < self.burn_threshold and val < self.burn_threshold:
            return ('burn', worst_card)
        return ('play', best_card, slot)

class BalancedBot(Bot):
    # Plays the best-fit card if it clears a synergy bar (build columns
    # deliberately); otherwise plays the chaff card so the good cards in
    # hand keep accumulating toward the hidden 5th hand. Burns true dead cards.
    name="balanced"
    synergy_bar = 8.0     # only "commit" a card to a column if it meaningfully helps
    burn_threshold = 1.0
    def act(self, hand, own_table, opp_table, burned):
        open_slots = [i for i in range(4) if len(own_table[i])<5]
        if not open_slots:
            return ('burn', random.choice(hand))
        best = {}
        for c in hand:
            scores = [(fit_score(c, own_table[i]), i) for i in open_slots]
            scores.sort(reverse=True)
            best[c] = scores[0]
        best_card = max(hand, key=lambda c: best[c][0])
        val, slot = best[best_card]
        worst_card = min(hand, key=lambda c: best[c][0])
        wval, wslot = best[worst_card]
        if val >= self.synergy_bar:
            return ('play', best_card, slot)
        if not burned and wval < self.burn_threshold:
            return ('burn', worst_card)
        return ('play', worst_card, wslot)

random.seed(7)
print("---fixed heuristics---")
print("Build vs Random:", tournament(BuildBot, RandomBot, 3000))
print("Build vs Greedy(hoard):", tournament(BuildBot, GreedyBot, 3000))
print("Balanced vs Random:", tournament(BalancedBot, RandomBot, 3000))
print("Balanced vs Build:", tournament(BalancedBot, BuildBot, 3000))
print("Balanced vs Greedy(hoard):", tournament(BalancedBot, GreedyBot, 3000))
print("Focus3(build variant) - reuse Build as base, vs Balanced:")

class PuntBuildBot(Bot):
    # Deliberately sacrifices one column (punt_col): fills it fast with
    # otherwise-useless low cards, while using Build logic (commit best-fit
    # card) on the other 3 columns + lets overflow accumulate for hidden hand.
    name="puntbuild"
    punt_col = 3
    burn_threshold = 1.5
    def act(self, hand, own_table, opp_table, burned):
        all_open = [i for i in range(4) if len(own_table[i])<5]
        if not all_open:
            return ('burn', random.choice(hand))
        focus_open = [i for i in all_open if i != self.punt_col]
        best = {}
        for c in hand:
            scores = [(fit_score(c, own_table[i]), i) for i in all_open]
            scores.sort(reverse=True)
            best[c] = scores[0]
        # find best card/slot restricted to the 3 focus columns
        if focus_open:
            focus_best = {}
            for c in hand:
                scores = [(fit_score(c, own_table[i]), i) for i in focus_open]
                scores.sort(reverse=True)
                focus_best[c] = scores[0]
            best_card = max(hand, key=lambda c: focus_best[c][0])
            val, slot = focus_best[best_card]
            worst_card = min(hand, key=lambda c: best[c][0])
            wval, wslot = best[worst_card]
            if not burned and wval < self.burn_threshold and val < self.burn_threshold:
                return ('burn', worst_card)
            if val >= 1.5 or self.punt_col not in all_open:
                return ('play', best_card, slot)
            # dump lowest-rank card into punt column to close it fast
            dump = min(hand, key=lambda c: c[0])
            return ('play', dump, self.punt_col)
        else:
            best_card = max(hand, key=lambda c: best[c][0])
            val, slot = best[best_card]
            return ('play', best_card, slot)

random.seed(11)
print("PuntBuild vs Random:", tournament(PuntBuildBot, RandomBot, 3000))
print("PuntBuild vs Build:", tournament(PuntBuildBot, BuildBot, 3000))
print("PuntBuild vs Balanced:", tournament(PuntBuildBot, BalancedBot, 3000))

class AdaptiveBot(Bot):
    # Build-style bot that also reads the opponent's OPEN columns: it
    # discounts investment in columns where the opponent already has a
    # commanding, hard-to-catch lead, and prioritizes columns still in play.
    name="adaptive"
    burn_threshold = 1.5
    def slot_weight(self, i, own_table, opp_table):
        opp_partial = opp_table[i]
        own_partial = own_table[i]
        if len(opp_partial) >= 3:
            opp_cat = hand_rank(opp_partial)[0]
            own_cat = hand_rank(own_partial)[0] if own_partial else 0
            slots_left_own = 5 - len(own_partial)
            if opp_cat >= 3 and own_cat < 1 and slots_left_own <= 2:
                return 0.25   # likely lost cause, deprioritize
            if opp_cat >= 2 and own_cat < opp_cat and slots_left_own <= 1:
                return 0.4
        return 1.0
    def act(self, hand, own_table, opp_table, burned):
        open_slots = [i for i in range(4) if len(own_table[i])<5]
        if not open_slots:
            return ('burn', random.choice(hand))
        best = {}
        for c in hand:
            scores = [(fit_score(c, own_table[i]) * self.slot_weight(i, own_table, opp_table), i)
                      for i in open_slots]
            scores.sort(reverse=True)
            best[c] = scores[0]
        best_card = max(hand, key=lambda c: best[c][0])
        val, slot = best[best_card]
        worst_card = min(hand, key=lambda c: best[c][0])
        wval, wslot = best[worst_card]
        if not burned and wval < self.burn_threshold and val < self.burn_threshold:
            return ('burn', worst_card)
        return ('play', best_card, slot)

random.seed(23)
print("Adaptive vs Random:", tournament(AdaptiveBot, RandomBot, 3000))
print("Adaptive vs Build:", tournament(AdaptiveBot, BuildBot, 3000))
print("Adaptive vs Balanced:", tournament(AdaptiveBot, BalancedBot, 3000))

# ============================================================
# DEEPER EXPERIMENTS
# ============================================================

def fit_score_w(card, slot_cards, rank_w=12, suit_w=4, straight_w=1.5, high_w=0.05):
    r,s = card
    if len(slot_cards)>=5: return -999
    score = 0
    ranks_in = [c[0] for c in slot_cards]
    suits_in = [c[1] for c in slot_cards]
    rc = collections.Counter(ranks_in); sc = collections.Counter(suits_in)
    score += rc.get(r,0)*rank_w
    score += sc.get(s,0)*suit_w
    if slot_cards:
        mind = min(abs(r-x) for x in ranks_in)
        if mind<=4: score += max(0,5-mind)*straight_w
    score += r*high_w
    return score

class WeightedBuildBot(Bot):
    name="wbuild"
    rank_w=12; suit_w=4; straight_w=1.5; burn_threshold=1.5
    def act(self, hand, own_table, opp_table, burned):
        open_slots = [i for i in range(4) if len(own_table[i])<5]
        if not open_slots:
            return ('burn', random.choice(hand))
        best={}
        for c in hand:
            scores=[(fit_score_w(c, own_table[i], self.rank_w, self.suit_w, self.straight_w), i) for i in open_slots]
            scores.sort(reverse=True); best[c]=scores[0]
        best_card=max(hand, key=lambda c: best[c][0]); val,slot=best[best_card]
        worst_card=min(hand, key=lambda c: best[c][0]); wval,_=best[worst_card]
        if not burned and wval<self.burn_threshold and val<self.burn_threshold:
            return ('burn', worst_card)
        return ('play', best_card, slot)

class PairHeavy(WeightedBuildBot):
    name="pairheavy"; rank_w=12; suit_w=1; straight_w=0.5
class FlushHeavy(WeightedBuildBot):
    name="flushheavy"; rank_w=6; suit_w=10; straight_w=0.5
class FlushOnly2Plus(WeightedBuildBot):
    # only value suit synergy once already 2+ of that suit in the slot (avoid chasing lone suits)
    name="flush2plus"
    def act(self, hand, own_table, opp_table, burned):
        open_slots=[i for i in range(4) if len(own_table[i])<5]
        if not open_slots: return ('burn', random.choice(hand))
        def score(c,slot):
            r,s=c
            if len(slot)>=5: return -999
            ranks_in=[x[0] for x in slot]; suits_in=[x[1] for x in slot]
            rc=collections.Counter(ranks_in); sc=collections.Counter(suits_in)
            sco = rc.get(r,0)*12
            if sc.get(s,0)>=2: sco += sc.get(s,0)*10   # only chase flush once committed (2+)
            elif sc.get(s,0)==1: sco += 1               # tiny nudge, don't force it
            if slot:
                mind=min(abs(r-x) for x in ranks_in)
                if mind<=4: sco += max(0,5-mind)*1.0
            sco += r*0.05
            return sco
        best={}
        for c in hand:
            scores=[(score(c, own_table[i]), i) for i in open_slots]
            scores.sort(reverse=True); best[c]=scores[0]
        best_card=max(hand, key=lambda c: best[c][0]); val,slot=best[best_card]
        worst_card=min(hand, key=lambda c: best[c][0]); wval,_=best[worst_card]
        if not burned and wval<1.5 and val<1.5:
            return ('burn', worst_card)
        return ('play', best_card, slot)

print("=== FLUSH/PAIR EMPHASIS ===")
random.seed(101)
print("PairHeavy vs FlushHeavy:", tournament(PairHeavy, FlushHeavy, 3000))
print("FlushOnly2Plus vs PairHeavy:", tournament(FlushOnly2Plus, PairHeavy, 3000))
print("FlushOnly2Plus vs FlushHeavy:", tournament(FlushOnly2Plus, FlushHeavy, 3000))
print("PairHeavy vs BuildBot(orig):", tournament(PairHeavy, BuildBot, 3000))

print("=== OPENINGS ===")
class SpreadOpenBot(PairHeavy):
    # For the first 4 of the player's own plays, force one card into each
    # distinct empty slot (maximize flexibility/information before committing).
    name="spreadopen"
    def act(self, hand, own_table, opp_table, burned):
        plays_made = sum(len(s) for s in own_table)
        empties = [i for i in range(4) if len(own_table[i])==0]
        if plays_made < 4 and empties:
            # play our currently weakest card into an untouched slot (cheap scouting)
            c = min(hand, key=lambda c: c[0])
            return ('play', c, empties[0])
        return super().act(hand, own_table, opp_table, burned)

class StackOpenBot(PairHeavy):
    # For the first 3 plays, deliberately pile into slot 0 regardless of fit,
    # trying to force early pair luck via raw volume.
    name="stackopen"
    def act(self, hand, own_table, opp_table, burned):
        plays_made = sum(len(s) for s in own_table)
        if plays_made < 3 and len(own_table[0])<5:
            c = min(hand, key=lambda c: c[0])
            return ('play', c, 0)
        return super().act(hand, own_table, opp_table, burned)

random.seed(303)
print("SpreadOpen vs PairHeavy:", tournament(SpreadOpenBot, PairHeavy, 3000))
print("StackOpen vs PairHeavy:", tournament(StackOpenBot, PairHeavy, 3000))
print("SpreadOpen vs StackOpen:", tournament(SpreadOpenBot, StackOpenBot, 3000))

print("=== MATCHUP TARGETING: reinforce lead vs attack weak vs contest strong ===")

def partial_strength(cards):
    if not cards: return -1
    return hand_rank(cards)[0]

class ReinforceLeadBot(PairHeavy):
    name="reinforce"
    def act(self, hand, own_table, opp_table, burned):
        open_slots=[i for i in range(4) if len(own_table[i])<5]
        if not open_slots: return ('burn', random.choice(hand))
        best={}
        for c in hand:
            scores=[]
            for i in open_slots:
                base = fit_score_w(c, own_table[i], 12,1,0.5)
                lead_bonus = partial_strength(own_table[i]) * 3   # favor own already-strong slots
                scores.append((base+lead_bonus, i))
            scores.sort(reverse=True); best[c]=scores[0]
        best_card=max(hand, key=lambda c: best[c][0]); val,slot=best[best_card]
        worst_card=min(hand, key=lambda c: best[c][0]); wval,_=best[worst_card]
        if not burned and wval<1.5 and val<1.5: return ('burn', worst_card)
        return ('play', best_card, slot)

class AttackWeakBot(PairHeavy):
    name="attackweak"
    def act(self, hand, own_table, opp_table, burned):
        open_slots=[i for i in range(4) if len(own_table[i])<5]
        if not open_slots: return ('burn', random.choice(hand))
        best={}
        for c in hand:
            scores=[]
            for i in open_slots:
                base = fit_score_w(c, own_table[i], 12,1,0.5)
                weak_bonus = -partial_strength(opp_table[i]) * 3   # favor slots where opp is weak
                scores.append((base+weak_bonus, i))
            scores.sort(reverse=True); best[c]=scores[0]
        best_card=max(hand, key=lambda c: best[c][0]); val,slot=best[best_card]
        worst_card=min(hand, key=lambda c: best[c][0]); wval,_=best[worst_card]
        if not burned and wval<1.5 and val<1.5: return ('burn', worst_card)
        return ('play', best_card, slot)

class ContestStrongBot(PairHeavy):
    name="conteststrong"
    def act(self, hand, own_table, opp_table, burned):
        open_slots=[i for i in range(4) if len(own_table[i])<5]
        if not open_slots: return ('burn', random.choice(hand))
        best={}
        for c in hand:
            scores=[]
            for i in open_slots:
                base = fit_score_w(c, own_table[i], 12,1,0.5)
                strong_bonus = partial_strength(opp_table[i]) * 3   # favor slots where opp is strong (race them)
                scores.append((base+strong_bonus, i))
            scores.sort(reverse=True); best[c]=scores[0]
        best_card=max(hand, key=lambda c: best[c][0]); val,slot=best[best_card]
        worst_card=min(hand, key=lambda c: best[c][0]); wval,_=best[worst_card]
        if not burned and wval<1.5 and val<1.5: return ('burn', worst_card)
        return ('play', best_card, slot)

random.seed(404)
bots = {'PairHeavy':PairHeavy,'Reinforce':ReinforceLeadBot,'AttackWeak':AttackWeakBot,'ContestStrong':ContestStrongBot}
names = list(bots)
for i in range(len(names)):
    for j in range(i+1,len(names)):
        n1,n2 = names[i],names[j]
        r = tournament(bots[n1], bots[n2], 2000)
        print(f"{n1} vs {n2}: {r}")

print("=== CAPSTONE: combine spread-opening + attack-weak + pair-priority ===")
class UnifiedBot(Bot):
    name="unified"
    def act(self, hand, own_table, opp_table, burned):
        open_slots=[i for i in range(4) if len(own_table[i])<5]
        if not open_slots: return ('burn', random.choice(hand))
        plays_made = sum(len(s) for s in own_table)
        empties=[i for i in range(4) if len(own_table[i])==0]
        if plays_made < 4 and empties:
            c = min(hand, key=lambda c: c[0])
            return ('play', c, empties[0])
        best={}
        for c in hand:
            scores=[]
            for i in open_slots:
                base = fit_score_w(c, own_table[i], 12, 1, 0.5)
                weak_bonus = -partial_strength(opp_table[i]) * 3
                scores.append((base+weak_bonus, i))
            scores.sort(reverse=True); best[c]=scores[0]
        best_card=max(hand, key=lambda c: best[c][0]); val,slot=best[best_card]
        worst_card=min(hand, key=lambda c: best[c][0]); wval,_=best[worst_card]
        if not burned and wval<1.5 and val<1.5: return ('burn', worst_card)
        return ('play', best_card, slot)

random.seed(909)
print("Unified vs PairHeavy:", tournament(UnifiedBot, PairHeavy, 3000))
print("Unified vs AttackWeak:", tournament(UnifiedBot, AttackWeakBot, 3000))
print("Unified vs Random:", tournament(UnifiedBot, RandomBot, 2000))
