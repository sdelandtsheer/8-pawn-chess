# Bot Principles For 8-Pawn Chess

The game is a race plus a zugzwang fight. Pawns only move forward, so every move
spends a finite tempo. Captures can win material, but they also change lanes and
often create or destroy passed-pawn races. The bot should therefore reason about
forced races, reserve tempi, opposition-like blocking, and fatal pawn breaks.

## Core Mental Model

- A move is not automatically useful. Every non-capturing move spends one tempo
  from that pawn's remaining race budget.
- The side with fewer safe waiting moves often loses even if material is equal.
- The decisive question is often: "Who runs out of non-losing moves first?"
- Captures are lane changes. They can remove a blocker or abandon a blockade.
- En passant is a tactical pin on double moves: any double move beside an enemy
  pawn must be checked as if it offers a capture immediately.
- The board decomposes partly into files and adjacent-file interactions, but
  captures couple neighboring files, so local evaluations must be merged.

## Immediate Tactics

- A pawn on rank 7 for White or rank 2 for Black is a direct one-ply threat.
- A pawn that cannot be stopped by a pawn directly ahead or diagonally ahead is
  usually decisive.
- Any move allowing the opponent an immediate promotion is losing unless it also
  promotes immediately.
- Any move that creates an unstoppable passed pawn is usually equivalent to a
  forced win.
- Capturing an advanced dangerous pawn is often mandatory even if another move
  looks active.
- En passant must be considered before ordinary race logic because it can erase
  a newly advanced pawn and change the lane count.

## Fatal Mistakes

- Advancing a pawn two squares when it can be captured en passant and the
  captured pawn was needed as a blocker or race winner.
- Moving a blocker off a file and giving the opponent a clean path to promotion.
- Capturing sideways with the only pawn that was stopping a passed pawn.
- Creating a protected passer for the opponent by making a "natural" recapture.
- Spending the last safe tempo while the opponent still has a harmless waiting
  pawn.
- Pushing a rear pawn that blocks one's own more advanced pawn.
- Ignoring the opponent's quiet threat to run out of moves: not every losing move
  is a capture or promotion tactic.
- Evaluating material instead of races. One extra pawn can be irrelevant if it is
  blocked and has no useful tempi.

## Tempo And Zugzwang Accounting

- Count safe moves, not just legal moves.
- A safe move is one that does not allow immediate promotion, does not create an
  unstoppable passer, and does not abandon a necessary blockade.
- Reserve tempi matter: back-rank pawns that can still move one or two squares
  may be valuable purely as waiting moves.
- Doubles are optional tempo compression. Playing a double spends two ranks in
  one move and may lose because it reduces future waiting capacity.
- A side with a forced passed-pawn race wants to reduce irrelevant tempi; a side
  defending wants to preserve safe waiting moves.
- If all moves worsen the position, choose the one that maximizes distance to
  loss. This mirrors exact DTM behavior.

## Passed Pawn Rules

- A passed pawn is strong only if its path cannot be occupied or captured in
  time by neighboring enemy pawns.
- A protected passer is much stronger than an unprotected passer because
  capturing it may open another pawn.
- A connected pair of advanced pawns can be winning even when neither pawn is
  individually unstoppable.
- Isolated advanced pawns are tactical targets: the opponent may be forced to
  capture them, but if capture is possible without losing tempo parity, they are
  overextended.
- A pawn one step from promotion dominates the position; all other evaluation
  should become secondary.

## Blockades

- Pawns directly facing each other create fixed files and tempo reservoirs.
- A blockade is good if it freezes an opponent pawn while preserving moves
  elsewhere.
- A blockade is bad if it leaves the player with no safe moves elsewhere.
- Breaking a blockade by capture must be evaluated as a race, not as material.
- Sometimes the winning move is to avoid a capture and force the opponent to
  move the blocking structure first.

## Captures

- Captures reduce material and often reduce total available tempi.
- A capture can be losing if it opens the capturing pawn to a faster enemy race.
- Recaptures are not automatic. The correct move may be a quiet pawn push that
  changes the race count.
- Capturing toward the center tends to increase future capture options; capturing
  toward the edge tends to reduce them, but may create a clearer passer.
- Captures that leave the opponent with only losing replies are stronger than
  captures that merely win a pawn.

## Candidate Move Ordering For A Strong Bot

- First: immediate promotions.
- Second: moves that prevent opponent immediate promotions.
- Third: captures of dangerous advanced pawns.
- Fourth: moves creating unstoppable or protected passers.
- Fifth: moves preserving necessary blockades.
- Sixth: quiet moves that preserve or increase safe tempo count.
- Last: double moves exposed to en passant, blockade-abandoning captures, and
  moves that spend the final safe tempo.

## Search Ideas

- Use selective proof search rather than full-width brute force.
- Always extend lines with pawns on the 7th/2nd rank, en passant rights,
  captures of advanced pawns, and newly created passers.
- Use quiescence around promotion threats and en passant, because shallow search
  is especially misleading there.
- Use transposition keys with normalized en passant, as before.
- Use exact DTM when the remaining material or active region is small enough.
- Use iterative deepening with a proof/disproof score: proven win, proven loss,
  unknown with heuristic ordering.
- In losing positions, optimize for longest resistance, not material.

## Evaluation Features

- Immediate terminal status.
- Minimum promotion distance for each side's best passer.
- Whether the path is clear.
- Whether enemy pawns can intercept from adjacent files in time.
- Number of safe legal moves for each side.
- Number of reserve double moves still available.
- Frozen/blockaded pawn count.
- Advanced-pawn danger score.
- En passant vulnerability score.
- Connected-passer and protected-passer bonuses.
- Penalty for moving a necessary blocker.

## Practical Bot Plan

- Keep a pure browser rules engine. The current browser implementation is
  `browser/wix_width8_zugzwang.html`.
- Add tactical detectors: immediate win, immediate loss, en passant danger,
  passed-pawn race, necessary blocker.
- Add move ordering based on the principles above.
- Add bounded proof search with extensions for forcing moves.
- Add a fallback evaluator based mainly on race distance and safe-tempo count.
- Cache searched positions in memory during a game.
- Prefer deterministic play for reproducibility.

## Guiding Rule

The bot should not ask "Which move looks good?" It should ask:

```text
Which moves do not lose, and among those, which one gives the opponent the
fewest non-losing replies?
```

## Current Implementation Note

The `zugzwang` bot follows this rule as a priority ordering instead of a blended
weighted score. Width-4 testing showed this is stronger than the broader
`principle` bot.

## Mirror Copycat Finding

The natural Black idea "copy White's move on the mirrored file/rank" is not a
win in this game. It preserves symmetry, but it also preserves White's first-move
tempo.

Example pattern:

```text
1. h4 h5 2. g4 g5 3. hxg5 hxg4 4. g6 g3 5. g7 g2 6. g8
```

Black would mirror with `...g1` next, but White has already won. The immediate
terminal rule matters: a copied race one ply later is too late.

So symmetry is not enough. Black needs an active deviation that prevents White's
breakthrough, not a blind copy.
