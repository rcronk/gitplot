# Visible Git — YouTube Series Curriculum

**Series tagline:** *Stop memorizing commands. Start seeing what they do.*

Every episode runs `visigit --monitor` in one terminal while git commands run in another.
The diagram updates live. Viewers watch the DAG change rather than guessing what happened.

---

## Series Overview

| # | Tier | Title | Mode | Commands |
|---|------|-------|------|----------|
| 01 | Setup | See Your Git: Setting Up a Live Repository Visualizer | all | install |
| 02 | Beginner | Your First Repository: Watching the Graph Appear | normal | init, add, commit |
| 03 | Beginner | Branches Aren't Copies: What Branching Really Does | normal | branch, checkout -b, switch |
| 04 | Beginner | The Merge Diamond: Fast-Forward vs No-Fast-Forward | normal + branch | merge, merge --no-ff |
| 05 | Beginner | Resolving Merge Conflicts: What MERGE_HEAD Shows You | normal | merge (conflict), add, commit, merge --abort |
| 06 | Beginner | Reset Demystified: Three Pointer Moves, Not Three Commands | normal | reset --soft/--mixed/--hard |
| 07 | Beginner | Undo Without Fear: revert vs amend (vs reset) | normal | revert, commit --amend |
| 08 | Beginner | Don't Panic: Detached HEAD Explained and Escaped | normal | checkout SHA, checkout -b |
| 09 | Intermediate | Merge vs Rebase: Same Code, Completely Different History | normal | merge, rebase |
| 10 | Intermediate | origin/main Is Not main: Remote Tracking Branches | normal | remote, fetch, pull, push |
| 11 | Intermediate | Two Repos, One Screen: Watching local and origin Together | all | clone, push, fetch, pull (bare origin) |
| 12 | Intermediate | Stash Is a Secret Commit: What git stash Actually Creates | verbose | stash, stash pop, stash list |
| 13 | Intermediate | Cherry-Pick: Copying a Commit (and Why the SHA Changes) | normal | cherry-pick |
| 14 | Intermediate | You Didn't Lose It: Finding Commits with git reflog | normal | reflog, reset --hard, checkout SHA |
| 15 | Intermediate | Git's Safety Nets: ORIG_HEAD, FETCH_HEAD, and Friends | normal | (observe pseudo-refs) |
| 16 | Advanced | Rewrite History: Interactive Rebase, Squash, and Fixup | normal | rebase -i |
| 17 | Advanced | Tags Are Just Pointers (Until They Aren't): Annotated vs Lightweight | normal | tag, tag -a |
| 18 | Advanced | Binary Search Your Bug: git bisect and the Commit Graph | normal | bisect start/good/bad/reset |
| 19 | Advanced | Two Branches, One Checkout: git worktree Explained | branch | worktree add/list/remove |
| 20 | Advanced | Force Push Is Destroying Someone's History: Here's the Proof | normal | push --force, push --force-with-lease |
| 21 | Internals | Inside a Commit: blob, tree, commit — Git's Four Object Types | verbose | commit (step through) |
| 22 | Internals | Submodules vs Subtrees: Pointer or Merged Files? | verbose | submodule add, subtree add |
| 23 | Internals | Same File, Same SHA: How Git Never Stores the Same Content Twice | verbose | add, commit (cross-commit reuse) |
| 24 | Internals | The Staging Area Exposed: What git add Actually Does to the Object Store | verbose | add, restore --staged, rm --cached |
| 25 | Internals | All the Way Down: git cat-file, .git/objects, and Pack Files | verbose + terminal | cat-file -p/-t, ls .git/objects/ |

---

## Tier 0 — Setup

---

### EP 01 — Setup — See Your Git: Setting Up a Live Repository Visualizer

**visigit mode:** demo of all three  
**Target length:** 5–8 min  
**Commands covered:** git init, pip install

#### YouTube Title
> See Your Git: Live Repository Diagrams That Update as You Type Commands

#### YouTube Description
> Stop guessing what git commands do — watch them happen. This video sets up visigit, a free tool that turns any git repository into a live diagram. Every command you run updates the graph in real time. Install it in under five minutes and you'll never memorize git blindly again.

#### Outline
| Time | Section |
|------|---------|
| 0:00 | Hook: show monitor mode updating live as git commands run |
| 0:45 | What visigit is and why it exists |
| 1:30 | Prerequisites: git (2.28+ required for `git init -b`; record on the latest stable git and state the version on-screen), Python 3.9+, graphviz (`apt install graphviz`) |
| 2:30 | Install visigit (`pip install -e .` or from source) |
| 3:30 | Quick demo: `visigit` on an existing repo — three modes at a glance |
| 4:30 | Set up the two-terminal workflow: visigit in Terminal A, git in Terminal B |
| 5:30 | Teaser of what's coming in the series |

#### Key Visual Moments
- Normal mode: collapse of boring commit chains into summary nodes
- Branch mode: topology graph — branches as nodes, fork points visible
- Verbose mode: trees and blobs appearing under each commit
- New nodes highlighted in gold on every monitor update

---

## Tier 1 — Beginner: Git Fundamentals

---

### EP 02 — Beginner — Your First Repository: Watching the Graph Appear

**visigit mode:** normal  
**Target length:** 10–12 min  
**Commands covered:** git init, git status, git add, git commit, git log

#### YouTube Title
> git init, add, commit — Watch the Commit Graph Build Itself in Real Time

#### YouTube Description
> You've run git init and git commit a hundred times. But do you know what they actually create? This video uses visigit to show you the moment HEAD, a branch ref, and your first commit node appear in the graph — and how the chain grows with every new commit. By the end you'll understand exactly what git status and git log are reporting.

#### Outline
| Time | Section |
|------|---------|
| 0:00 | Start the monitor: `visigit --monitor --viewer html` in Terminal A |
| 0:45 | `git init -b main` — graph is empty, why? |
| 1:30 | Create a file, `git status` — untracked, nothing in graph yet |
| 2:15 | `git add README.md` — still nothing? (staging doesn't create a commit) |
| 3:00 | `git commit -m "initial"` — HEAD, main, and the first commit node appear at once |
| 4:30 | Explain the three nodes: HEAD ref → branch ref → commit node |
| 5:30 | Second commit: `echo "hello" > app.py && git add -A && git commit -m "add app"` |
| 6:30 | Parent edge appears: newer commit → older commit |
| 7:30 | Third commit: the chain grows — `git log` matches exactly what's in the graph |
| 8:30 | Boring chain collapse: add 5 quick commits and watch them become one summary node |
| 10:00 | `--commit-details` flag: author, message, date appear on each node |
| 11:00 | Recap: what the three-tier HEAD → branch → commit structure means |

#### Key Visual Moments
- Empty graph before first commit
- Simultaneous appearance of HEAD, branch ref, and commit node on first `git commit`
- Parent edge direction (newest commit on the right with default RL layout)
- Boring chain collapsing into `a1b2c3 (N) f4e5d6` summary node

---

### EP 03 — Beginner — Branches Aren't Copies: What Branching Really Does

**visigit mode:** normal  
**Target length:** 10–13 min  
**Commands covered:** git branch, git checkout -b, git switch -c, git switch, git checkout

#### YouTube Title
> git branch Doesn't Copy Anything — Here's What It Actually Does to Your Repository

#### YouTube Description
> Most people think creating a branch copies their code. It doesn't — it creates a single pointer to an existing commit. Watch visigit show you the exact moment a branch label appears in the graph and how it splits from its sibling when you make your first commit. This one diagram will change how you think about branches forever.

#### Outline
| Time | Section |
|------|---------|
| 0:00 | Misconception: "branching makes a copy" — let's disprove it visually |
| 1:00 | Make two commits on main, watch the chain form |
| 2:00 | `git checkout -b feature` — only a new label appears on the same commit |
| 3:00 | HEAD moves to feature; main stays exactly where it was |
| 4:00 | `git switch` / `git checkout` — HEAD label moves between branch refs |
| 5:00 | First commit on feature: NOW the branches diverge — main left behind |
| 6:30 | Switch back to main — HEAD moves; feature tip stays |
| 7:30 | First commit on main: two branches pointing to different commits from the same parent |
| 8:30 | `git branch -v` output compared to what the graph shows |
| 9:30 | Deleting a branch: `git branch -d feature` — label disappears, commit still exists |
| 11:00 | Orphaned commits: when is it safe to delete? |

#### Key Visual Moments
- New branch label appearing on the same commit node as main
- HEAD arrow moving when you switch branches
- The moment of divergence: each branch gets its own commit
- Branch deletion removing the label but leaving the commit node until GC

---

### EP 04 — Beginner — The Merge Diamond: Fast-Forward vs No-Fast-Forward

**visigit mode:** normal (commit chain) + branch (topology)  
**Target length:** 12–15 min  
**Commands covered:** git merge, git merge --no-ff

#### YouTube Title
> git merge --no-ff Creates a Diamond — Here's What That Means and Why It Matters

#### YouTube Description
> There are two completely different graph shapes that can result from a merge: a straight line (fast-forward) or a diamond (no-fast-forward). This video shows both side by side in visigit so you can see exactly when git moves a pointer vs when it creates a real merge commit — and why that choice affects your project history permanently.

#### Outline
| Time | Section |
|------|---------|
| 0:00 | Two types of merge: set the stage |
| 1:00 | Build a diverged repo: main + feature both ahead of a common base |
| 2:30 | Fast-forward scenario: feature is strictly ahead of main |
| 3:30 | `git merge feature` — main label jumps to feature tip; no new commit node |
| 4:30 | Why it's called "fast-forward": the pointer simply advances |
| 5:30 | Reset and rebuild: diverged scenario where both branches have unique commits |
| 6:30 | `git merge feature --no-ff` — a merge commit appears with TWO parent edges |
| 7:30 | The diamond: base → left path → merge commit ← right path ← base |
| 8:30 | Switch to `--mode branch`: see the topology in branch view |
| 9:30 | When to use each: open-source vs team workflows |
| 11:00 | Merge conflicts: what they look like (brief; deep dive in a separate video) |
| 12:30 | Merge commit has two parents — show the edges in the graph |

#### Key Visual Moments
- Fast-forward: branch label teleports, no new commit node
- No-FF: merge commit node with two inbound parent edges
- Branch mode: diamond becomes a fork-point node connecting two branch labels
- `--commit-details` showing "Merge branch 'feature' into main" message on the merge commit

---

### EP 05 — Beginner — Resolving Merge Conflicts: What MERGE_HEAD Shows You

**visigit mode:** normal  
**Target length:** 10–12 min  
**Commands covered:** git merge (conflict), git status, git add, git commit, git merge --abort

#### YouTube Title
> Merge Conflicts Aren't Scary: git Writes MERGE_HEAD and visigit Shows You Exactly Where You Are

#### YouTube Description
> A merge conflict stops git mid-merge and leaves you in a state most people find terrifying. It shouldn't be. When a merge conflicts, git writes a ref called MERGE_HEAD pointing at the commit you're merging in — and visigit shows it right in the graph, so you can always see both sides of the merge and exactly what you're resolving. This video walks a conflict from start to finish: what MERGE_HEAD is, how to resolve it, and how to bail out with --abort.

#### Outline
| Time | Section |
|------|---------|
| 0:00 | The fear: "CONFLICT (content): Merge conflict in ..." |
| 1:00 | Set up two branches that edit the same line |
| 2:00 | `git merge feature` — it stops; the working tree is now mid-merge |
| 2:45 | visigit shows MERGE_HEAD pointing at the feature commit — both sides visible |
| 3:45 | `git status` — "Unmerged paths"; what the index looks like during a conflict |
| 4:45 | Open the file: the `<<<<<<<`, `=======`, `>>>>>>>` markers explained |
| 5:45 | Resolve, then `git add` the file — the conflict is staged |
| 6:45 | `git commit` — the merge commit appears with TWO parents; MERGE_HEAD disappears |
| 7:45 | The escape hatch: `git merge --abort` — back to before the merge, MERGE_HEAD gone |
| 8:45 | Why MERGE_HEAD matters: it's how git (and you) remember what's being merged |
| 10:00 | Recap: a conflict is just a paused merge; MERGE_HEAD marks the other side |

#### Key Visual Moments
- MERGE_HEAD node appearing the moment a merge conflicts, pointing at the merged commit
- Both merge parents visible simultaneously while the conflict is unresolved
- The merge commit forming (two parent edges) and MERGE_HEAD vanishing on `git commit`
- `git merge --abort` removing MERGE_HEAD and returning HEAD to the pre-merge tip

---

### EP 06 — Beginner — Reset Demystified: Three Pointer Moves, Not Three Commands

**visigit mode:** normal  
**Target length:** 12–14 min  
**Commands covered:** git reset --soft, git reset --mixed, git reset --hard

#### YouTube Title
> git reset --soft vs --mixed vs --hard: Watch the Branch Pointer Move Three Different Ways

#### YouTube Description
> git reset is one of the most feared commands in git — and the most misunderstood. All three modes do the same thing to the branch pointer (move it back), so in normal mode they produce an identical graph; what they differ on is how much of your work they preserve, which you see in verbose mode. And the commit you reset past does not vanish — ORIG_HEAD still points to it. Watch visigit show you all of this, and you'll never confuse the three modes again.

#### Outline
| Time | Section |
|------|---------|
| 0:00 | The fear: "I ran git reset and lost my work" |
| 1:00 | Build up a chain: three commits, HEAD → main → C3 → C2 → C1 |
| 2:00 | What all three modes share: the branch pointer moves back |
| 3:00 | `git reset --soft HEAD~1` — main moves back to C2; C3 stays visible via the ORIG_HEAD ref (git's safety net); files are staged |
| 4:30 | Verify: `git status` shows staged changes; working tree unchanged |
| 5:30 | `git reset --mixed HEAD~1` — pointer moves again; staged changes cleared |
| 6:30 | Verify: `git status` shows unstaged changes; working tree still unchanged |
| 7:30 | `git reset --hard HEAD~1` — pointer moves; index AND working tree wiped |
| 8:30 | Verify: `git status` is clean; the files are gone |
| 9:30 | The unreachable commit: it still exists in `.git/objects` — show in verbose mode |
| 10:30 | When to use each: fixing the last commit vs recovering from disaster |
| 12:00 | Teaser: Episode 14 shows you how to recover from --hard with reflog |

#### Key Visual Moments
- Branch pointer moving back one commit with each reset
- The reset commit staying visible via the ORIG_HEAD ref (git keeps it — it is not lost), even though main no longer points to it
- The working tree / staging area state NOT visible in normal mode (point to verbose for that)
- Commit node that's "gone" from graph but visible again when you detach HEAD at its SHA

---

### EP 07 — Beginner — Undo Without Fear: revert vs amend (vs reset)

**visigit mode:** normal  
**Target length:** 11–13 min  
**Commands covered:** git revert, git commit --amend, (contrast with git reset)

#### YouTube Title
> git revert vs git commit --amend vs git reset: Three Ways to Undo, Three Different Graphs

#### YouTube Description
> "Undo" in git isn't one thing. revert ADDS a new commit that cancels an old one (safe to share). amend REWRITES your last commit (new SHA, the old one orphaned). reset MOVES the branch pointer back. They look similar in the terminal but do completely different things to the graph — and visigit makes the difference impossible to miss. By the end you'll always pick the right one.

#### Outline
| Time | Section |
|------|---------|
| 0:00 | Three "undos" that are nothing alike |
| 1:00 | Build a small history: a couple of commits |
| 2:00 | `git revert HEAD` — a NEW commit appears on top; the chain GROWS |
| 3:00 | Why revert is safe on shared branches: it doesn't rewrite anything |
| 4:00 | Contrast: `git reset` moves the pointer back (the EP06 mechanic) |
| 5:00 | `git commit --amend` — fix the last commit's message or content |
| 5:45 | Watch: the old commit VANISHES; a new SHA replaces it |
| 6:30 | The catch: amend writes NO ORIG_HEAD — the old commit is only in the reflog |
| 7:30 | Why the SHA changes: the message and content are part of the commit object |
| 8:30 | When to use each: revert (shared), amend (last local commit), reset (move the tip) |
| 9:30 | The golden rule: never amend or reset commits you've already pushed and shared |
| 11:00 | Recap: revert ADDS, amend REPLACES, reset MOVES |

#### Key Visual Moments
- revert: a new commit node appended (graph grows by one), the original commit untouched
- amend: the old commit node disappearing and a new-SHA node taking its place
- The absence of ORIG_HEAD after amend (unlike reset/rebase) — its old commit is truly gone from the graph
- Side-by-side mental model: ADD (revert) vs REPLACE (amend) vs MOVE (reset)

---

### EP 08 — Beginner — Don't Panic: Detached HEAD Explained and Escaped

**visigit mode:** normal  
**Target length:** 10–12 min  
**Commands covered:** git checkout SHA, git switch --detach, git checkout -b recovery, git switch -

#### YouTube Title
> "You are in 'detached HEAD' state" — What It Means and How to Escape

#### YouTube Description
> "You are in 'detached HEAD' state" is one of the most alarming messages in git. But it's not dangerous — it just means HEAD is pointing directly at a commit instead of through a branch. Watch visigit show you exactly what detached HEAD looks like in the graph, what happens to commits you make in that state, and the two ways to safely get back.

#### Outline
| Time | Section |
|------|---------|
| 0:00 | The scary message — read it aloud |
| 1:00 | Normal state: HEAD → branch → commit (three-tier) |
| 2:00 | `git checkout <sha>` on an older commit — HEAD now points directly at commit |
| 3:00 | Graph: HEAD → commit (two-tier; branch ref visible but disconnected from HEAD) |
| 4:00 | What happens if you make a commit in detached HEAD: orphan commit node |
| 5:30 | `git switch -` or `git checkout main` — HEAD reattaches to branch |
| 6:30 | The orphan commit: unreachable now but still in the object store |
| 7:30 | Escape route 2: `git checkout -b recovery` from detached HEAD |
| 8:30 | Graph: recovery branch label appears; the work is preserved |
| 9:30 | Common trigger: `git checkout <tag>` — same mechanism |
| 10:30 | Recap: detached HEAD = missing branch label, not corrupted repo |

#### Key Visual Moments
- Normal: HEAD → refs/heads/main → commit (HEAD node edges to branch node)
- Detached: HEAD → commit directly (branch ref is in graph but not connected to HEAD)
- Orphan commit made in detached HEAD state — unreachable after re-attaching
- New branch node appearing when you run `git checkout -b recovery`

---

## Tier 2 — Intermediate: Git Workflows

---

### EP 09 — Intermediate — Merge vs Rebase: Same Code, Completely Different History

**visigit mode:** normal  
**Target length:** 13–15 min  
**Commands covered:** git merge --no-ff, git rebase, git log --oneline --graph

#### YouTube Title
> git merge vs git rebase: Same Result, Completely Different Graph — See Both Live

#### YouTube Description
> Merge and rebase both get your changes integrated, but they leave completely different histories behind. This video runs both operations on identical repos and shows you the graphs side by side: a merge creates a diamond with a merge commit; a rebase replays your commits with new SHAs onto a straight line. By the end you'll know which to choose and why.

#### Outline
| Time | Section |
|------|---------|
| 0:00 | Same goal, different tools — why this matters |
| 1:00 | Build the diverged scenario: main has a hotfix; feature has a new commit |
| 2:30 | Path A: `git merge feature --no-ff` — diamond shape, merge commit, two parents |
| 4:00 | Pros: preserves the true history; merge commit is explicit |
| 5:00 | Cons: noisy graph in a large project; every integration adds a node |
| 6:00 | Reset to diverged state; Path B: `git rebase main` from feature branch |
| 7:30 | Watch: NEW commit nodes appear with different SHAs; the original feature commit stays visible via ORIG_HEAD (git keeps it — rebase does not delete it) |
| 8:30 | The key insight: rebase does NOT move commits — it creates new ones |
| 9:30 | Linear history: feature replay sits directly on main's tip — clean `git log` |
| 10:30 | When to use merge: shared branches, open-source PRs, preserve context |
| 11:30 | When to use rebase: local feature cleanup, keeping a team's main branch linear |
| 12:30 | The golden rule of rebase: never rebase commits already on a shared branch |

#### Key Visual Moments
- Merge: diamond with merge commit node, two parent edges
- Rebase: new SHA nodes appear; the original (pre-rebase) commit stays reachable via the ORIG_HEAD ref — git's safety net, not deleted
- Linear history after rebase: single parent chain with no diamond
- `git log --oneline --graph` terminal output matching the visigit diagram exactly

---

### EP 10 — Intermediate — origin/main Is Not main: Remote Tracking Branches

**visigit mode:** normal  
**Target length:** 12–14 min  
**Commands covered:** git remote add, git fetch, git pull, git push, git branch -vv

#### YouTube Title
> origin/main Is Not main — How git fetch, pull, and push Move the Remote Tracking Pointer

#### YouTube Description
> There are actually two "main" branches in a typical repo: your local main and origin/main (the remote tracking ref). Most people conflate them until something goes wrong. This video uses visigit to show you both refs in the same graph, what happens when they drift apart, and exactly what fetch, pull, and push do to each pointer.

#### Outline
| Time | Section |
|------|---------|
| 0:00 | Clone a repo: two mains appear in the graph immediately |
| 1:30 | origin/main is a local snapshot of the remote — it doesn't update automatically |
| 2:30 | `git fetch` — origin/main pointer moves; local main stays behind |
| 3:30 | Graph: origin/main has moved ahead; local main trails |
| 4:30 | `git merge origin/main` (or `git pull`) — local main catches up |
| 5:30 | Ahead/behind: make a local commit, see main drift ahead of origin/main |
| 6:30 | `git push` — origin/main jumps to match local main |
| 7:30 | Diverged: both local and remote have unique commits (common team scenario) |
| 8:30 | `git pull --rebase` vs `git pull` (merge): different graph shapes |
| 9:30 | `--exclude-remotes` flag: hide remote refs when the graph gets busy |
| 11:00 | `git branch -vv`: read the ahead/behind numbers from the graph |

#### Key Visual Moments
- Clone: refs/remotes/origin/main and refs/heads/main both visible from the start
- Fetch: only origin/main moves; local main unchanged
- Push: origin/main catches up to local main
- Diverged: origin/main and main pointing to different commits on the same chain

---

### EP 11 — Intermediate — Two Repos, One Screen: Watching local and origin Together

**visigit mode:** all (two monitor sessions)  
**Target length:** 11–13 min  
**Commands covered:** git clone, git push, git fetch, git pull (with a bare "origin" on the same machine)

#### YouTube Title
> See Both Sides of git push/fetch: Visualize Your Repo AND origin Side by Side

#### YouTube Description
> origin/main is a snapshot inside your repo — but where's the ACTUAL origin? In this video we put a bare "origin" repository on the same machine and run a second `visigit --monitor` on it, so you watch BOTH graphs at once. Now push, fetch, and pull aren't mysterious: you see commits leave your repo and land in origin, and origin/main catch up — live, side by side.

#### Outline
| Time | Section |
|------|---------|
| 0:00 | The missing half: you've seen origin/main, but never origin itself |
| 1:00 | Make a bare origin: `git init --bare ../origin.git` (no working tree) |
| 2:00 | Terminal layout: `visigit --monitor` on your repo (left), on the bare origin (right) |
| 3:00 | `git push` — watch the commit appear in the origin graph; origin/main advances |
| 4:30 | Teammate simulation: commit in a second clone and push to origin |
| 5:30 | `git fetch` — origin/main moves in YOUR graph to match the origin graph |
| 6:30 | `git pull` (fetch + merge) — local main catches up; both graphs converge |
| 7:30 | A bare repo has no working tree: no Staged/Unstaged boxes, just the commit graph |
| 8:30 | Diverged: local and origin each advance — see it on both screens at once |
| 9:30 | Why bare: pushing to a non-bare repo's checked-out branch is rejected by default |
| 11:00 | Recap: push/fetch/pull are just commits moving between two real graphs |

#### Key Visual Moments
- Two visigit windows: your repo and the bare origin, updating independently
- A commit appearing in the origin graph the instant you push
- origin/main in your graph jumping to match origin after fetch
- The bare origin rendering as a pure commit graph (no index boxes — it has no working tree)

---

### EP 12 — Intermediate — Stash Is a Secret Commit: What git stash Actually Creates

**visigit mode:** verbose  
**Target length:** 10–12 min  
**Commands covered:** git stash, git stash list, git stash pop, git stash drop, git stash apply

#### YouTube Title
> git stash Creates a Real Commit — You Just Can't See It in Normal Mode

#### YouTube Description
> git stash feels like a magic shelf that saves your work temporarily. What it actually does is create a special commit hanging off a ref called refs/stash — and that commit is only visible in visigit's verbose mode. This video shows you the hidden object, how stash entries stack up, and what pop, apply, and drop each do to the graph.

#### Outline
| Time | Section |
|------|---------|
| 0:00 | The mystery: where does stashed work go? |
| 1:00 | Start in verbose monitor mode: `visigit --mode verbose --monitor` |
| 1:45 | Make uncommitted changes on a dirty working tree |
| 2:30 | `git stash` — watch the refs/stash node appear in the graph |
| 3:30 | The stash commit: it contains both your staged and unstaged changes |
| 4:30 | `git stash list` — stash@{0}, stash@{1}... each is a commit in the graph |
| 5:30 | `git stash` again with different changes — stash@{0} and stash@{1} both visible |
| 6:30 | `git stash pop` — stash ref disappears; changes re-enter the working tree |
| 7:30 | `git stash apply` vs `git stash pop`: apply leaves the stash entry; pop removes it |
| 8:30 | `git stash drop` — entry removed from graph |
| 9:30 | Why stash is a commit: it survives garbage collection; it has a SHA |
| 10:30 | Stash is only visible in verbose mode — explain why (include_stash flag) |

#### Key Visual Moments
- Stash refs ONLY appear in verbose mode (the first time students see this distinction)
- refs/stash → stash commit node appearing after `git stash`
- Multiple stash entries stacking up
- stash@{0} node disappearing on `git stash pop`

---

### EP 13 — Intermediate — Cherry-Pick: Copying a Commit (and Why the SHA Changes)

**visigit mode:** normal  
**Target length:** 10–12 min  
**Commands covered:** git cherry-pick, git cherry-pick --no-commit, git cherry-pick --abort

#### YouTube Title
> git cherry-pick Copies a Commit — But the SHA Changes Every Time. Here's Why.

#### YouTube Description
> cherry-pick lets you take one specific commit from any branch and replay it somewhere else. But the resulting commit always has a different SHA — even though the changes are identical. This video explains why using visigit: the parent commit is different, so the content of the commit object is different, so the SHA is different. You'll see it happen live.

#### Outline
| Time | Section |
|------|---------|
| 0:00 | The use case: hotfix on main that also needs to go to a release branch |
| 1:00 | Build the scenario: main and release/1.0 diverged from a common base |
| 2:00 | Make a critical fix commit on main; record its SHA |
| 3:00 | `git checkout release/1.0` |
| 3:30 | `git cherry-pick <sha>` — a NEW commit node appears on release/1.0 |
| 4:30 | New SHA despite same changes: show both nodes in graph; different SHAs, different parents |
| 5:30 | Why the SHA differs: the commit object contains the parent SHA — change the parent, change the SHA |
| 6:30 | `git cherry-pick --no-commit`: changes land in index; you commit manually |
| 7:30 | Multiple cherry-picks: each creates its own new node |
| 8:30 | Cherry-pick a merge commit: `--mainline` flag |
| 9:30 | When to prefer cherry-pick over merge/rebase |
| 10:30 | Downside: diverging histories can accumulate if overused |

#### Key Visual Moments
- Original commit node on main with SHA X
- New commit node on release/1.0 with SHA Y — same label content, different node identity
- Parent edge from Y to the release branch tip (not to X's parent)
- The original commit X still in the graph on main, untouched

---

### EP 14 — Intermediate — You Didn't Lose It: Finding Commits with git reflog

**visigit mode:** normal  
**Target length:** 12–14 min  
**Commands covered:** git reflog, git reset --hard, git checkout SHA, git branch recover

#### YouTube Title
> You Didn't Lose Your Commits — git reflog Is Git's Secret Safety Net

#### YouTube Description
> You ran git reset --hard or git rebase and now your commits are "gone." They're not — git keeps every commit in the object store for at least 30 days. git reflog shows you the history of where HEAD has been, giving you the SHA of every commit you've ever had checked out. This video shows you how to find and recover them using visigit to confirm the work is really still there.

#### Outline
| Time | Section |
|------|---------|
| 0:00 | The disaster scenario: commits gone after reset --hard |
| 1:00 | Build a chain: three commits on main |
| 2:00 | `git reset --hard HEAD~2` — main jumps back two commits; the old tip stays visible via ORIG_HEAD, but ORIG_HEAD only remembers ONE prior position |
| 3:00 | The trap: do another operation and ORIG_HEAD is overwritten — now where did the work go? |
| 3:30 | `git reflog` — full history of HEAD positions with SHAs |
| 4:30 | Find the SHA of the "lost" commit in the reflog output |
| 5:30 | `git checkout <lost-sha>` — detach HEAD at the commit; it REAPPEARS in visigit |
| 6:30 | The commit was never deleted — just unreachable from any ref |
| 7:30 | `git branch recover <lost-sha>` — new branch label rescues the work |
| 8:30 | `git checkout -` — return to main; the recover branch is still in the graph |
| 9:30 | Reflog for branch tips: `git reflog show main` |
| 10:30 | When reflog fails: commits older than 30 days get garbage collected |
| 11:30 | `git gc --prune=now` for demo: permanently remove unreachable objects |

#### Key Visual Moments
- The pre-reset tip staying visible via ORIG_HEAD after `reset --hard`; reflog recovering commits from BEFORE that, which ORIG_HEAD no longer remembers
- A "lost" commit reappearing when HEAD is detached at the SHA found in the reflog
- `git branch recover <sha>` making the commits permanently reachable again
- Before/after: the "lost" work visible in the graph once a branch ref points at it

---

### EP 15 — Intermediate — Git's Safety Nets: ORIG_HEAD, FETCH_HEAD, and Friends

**visigit mode:** normal  
**Target length:** 10–12 min  
**Commands covered:** observing ORIG_HEAD, FETCH_HEAD, MERGE_HEAD, CHERRY_PICK_HEAD, BISECT_HEAD

#### YouTube Title
> The Hidden Refs That Save You: ORIG_HEAD, FETCH_HEAD, and git's Other Safety Nets

#### YouTube Description
> You've seen them flash by: ORIG_HEAD after a reset, MERGE_HEAD during a conflict, FETCH_HEAD after a fetch. These are git's pointer files — special refs git writes so YOU (and git) can recover and reason about what just happened. Most tools hide them; visigit shows them. This video gathers them in one place so you understand the safety net under every "dangerous" command.

#### Outline
| Time | Section |
|------|---------|
| 0:00 | The refs you keep seeing but nobody explains |
| 1:00 | ORIG_HEAD: written by reset, rebase, and merge — the "where I was" pointer |
| 2:30 | Recover from `git reset --hard` using ORIG_HEAD, live |
| 3:30 | MERGE_HEAD: the other side of an in-progress merge (callback to EP05) |
| 4:30 | CHERRY_PICK_HEAD: the commit being applied during a cherry-pick conflict |
| 5:30 | FETCH_HEAD: what `git fetch` just brought down |
| 6:30 | BISECT_HEAD: where a bisect session is currently testing (callback to EP18) |
| 7:30 | The one exception: `git commit --amend` writes NO ORIG_HEAD (callback to EP07) |
| 8:30 | Why visigit shows these: they ARE refs — real pointers into the object store |
| 9:30 | The mental model: almost nothing is ever truly lost until git gc |
| 11:00 | Recap: every scary command leaves a breadcrumb — now you can see them |

#### Key Visual Moments
- ORIG_HEAD appearing after reset/rebase/merge, keeping the "old" tip reachable
- MERGE_HEAD / CHERRY_PICK_HEAD appearing only mid-operation, then vanishing on completion
- FETCH_HEAD and BISECT_HEAD shown as ordinary ref nodes with no edge label
- The contrast: amend leaves no safety net, so its old commit really is gone from the graph

---

## Tier 3 — Advanced: Power User Git

---

### EP 16 — Advanced — Rewrite History: Interactive Rebase, Squash, and Fixup

**visigit mode:** normal  
**Target length:** 13–15 min  
**Commands covered:** git rebase -i HEAD~N, squash, fixup, reword, drop, reorder

#### YouTube Title
> git rebase -i: Squash, Reorder, and Rewrite Commits — Watch the Graph Change

#### YouTube Description
> Interactive rebase lets you rewrite your local commit history before sharing it: squash five "WIP" commits into one, fix a typo in a commit message, drop a commit entirely, or reorder them. This video walks through each operation in visigit so you can see exactly which commit nodes change SHA, which disappear, and which survive untouched.

#### Outline
| Time | Section |
|------|---------|
| 0:00 | Why clean history matters before a PR |
| 1:00 | Build a messy branch: five commits including WIP, typos, and one accidental commit |
| 2:00 | `git rebase -i HEAD~5` — walk through the editor |
| 3:30 | `squash`: merge commit N into N-1 — two nodes become one, new SHA |
| 5:00 | `fixup`: same as squash but discard the squashed commit's message |
| 6:00 | `reword`: change a commit message — same content, new SHA because message is in the object |
| 7:00 | `drop`: remove a commit from the branch — it stays visible via ORIG_HEAD (the pre-rebase tip) until git gc |
| 8:00 | Reorder: swap two commit lines — graph order changes, SHAs change |
| 9:00 | After rebase: graph shows clean, linear history with new SHAs for every modified commit |
| 10:00 | Why ALL downstream SHAs change when you modify one commit in a chain |
| 11:30 | The golden rule: never rebase commits already pushed to a shared branch |
| 13:00 | `git push --force-with-lease` if you must — covered more in EP 20 |

#### Key Visual Moments
- Before: messy chain of 5 commit nodes
- During: new-SHA nodes appearing as operations apply; the original commits staying visible via ORIG_HEAD (the pre-rebase tip)
- After squash/fixup: fewer nodes, different SHAs
- Every commit after the rebased point has a new SHA (child SHAs change when parent SHA changes)

---

### EP 17 — Advanced — Tags Are Just Pointers (Until They Aren't): Annotated vs Lightweight

**visigit mode:** normal  
**Target length:** 10–12 min  
**Commands covered:** git tag, git tag -a, git tag -l, git push --tags, git describe

#### YouTube Title
> git tag vs git tag -a: Two Different Graph Nodes for Two Different Objects

#### YouTube Description
> A lightweight tag is just a ref that points to a commit — exactly like a branch, except it doesn't move. An annotated tag is a full git object with its own SHA, author, and message, sitting between the tag ref and the commit. This video shows you both in visigit's graph so you can see exactly what you're creating and why annotated tags are preferred for releases.

#### Outline
| Time | Section |
|------|---------|
| 0:00 | What tags are for: marking releases and milestones |
| 1:00 | `git tag v1.0` (lightweight) — a new tag ref appears directly pointing to the commit |
| 2:00 | One node: tag ref → commit (same as a branch, just doesn't move) |
| 3:00 | `git tag -a v2.0 -m "Release 2.0"` — two nodes: tag ref → tag object → commit |
| 4:30 | The tag object: it has its own SHA, tagger identity, timestamp, message |
| 5:30 | Why annotated tags are preferred: contain metadata, can be signed, shown by `git describe` |
| 6:30 | `git tag -l` — list all tags; cross-reference with graph |
| 7:30 | `git push --tags` — push all tags to remote |
| 8:30 | `git describe --tags` — finds nearest tag and measures distance in commits |
| 9:30 | Deleting a tag vs deleting a branch: same `git tag -d` / `git push origin :v1.0` |
| 10:30 | Signed tags: GPG signature stored in the tag object (brief mention, not deep-dived) |

#### Key Visual Moments
- Lightweight tag: single extra ref node pointing straight to commit
- Annotated tag: two nodes — tag ref node + tag object node with intermediate SHA
- Side-by-side in graph: v1.0 (lightweight) with one hop; v2.0 (annotated) with two hops

---

### EP 18 — Advanced — Binary Search Your Bug: git bisect and the Commit Graph

**visigit mode:** normal  
**Target length:** 11–13 min  
**Commands covered:** git bisect start, git bisect good, git bisect bad, git bisect reset, git bisect run

#### YouTube Title
> git bisect: Binary Search Your Commit History to Find Exactly When a Bug Appeared

#### YouTube Description
> A bug exists now that didn't exist six months ago. git bisect performs a binary search through your commit history, halving the search space at each step. This video shows the process in visigit: watch HEAD move through the graph as bisect narrows in on the exact commit that introduced the bug — often in just 7-10 steps through hundreds of commits.

#### Outline
| Time | Section |
|------|---------|
| 0:00 | The problem: something broke, you don't know when |
| 1:00 | Build a history with 16 commits; introduce a bug at commit 10 |
| 2:00 | `git bisect start` |
| 2:30 | `git bisect bad` — mark current HEAD as bad |
| 3:00 | `git bisect good <old-sha>` — mark a known good commit |
| 3:30 | HEAD moves to the midpoint — watch visigit show HEAD at the middle commit |
| 4:30 | Test, mark good or bad; HEAD moves again — bisect halves the range |
| 6:00 | After log2(16) = 4 steps: bisect identifies the exact commit |
| 7:00 | `git bisect log` — see the search path |
| 8:00 | `git bisect reset` — HEAD returns to original position |
| 9:00 | `git bisect run <test-script>` — fully automated bisect |
| 10:30 | Real-world tip: use `--max-commit-depth N` in visigit to limit graph depth during bisect |

#### Key Visual Moments
- HEAD node jumping to the midpoint commit after `git bisect start` + good/bad
- Each test step: HEAD moves to a new midpoint in the graph
- The bisect-identified commit highlighted as HEAD lands on it
- `git bisect reset` moving HEAD back to its original position

---

### EP 19 — Advanced — Two Branches, One Checkout: git worktree Explained

**visigit mode:** branch  
**Target length:** 10–12 min  
**Commands covered:** git worktree add, git worktree list, git worktree remove, git worktree prune

#### YouTube Title
> git worktree: Check Out Two Branches at the Same Time Without Stashing

#### YouTube Description
> Normally you can only have one branch checked out at a time. git worktree lets you check out additional branches into separate directories on disk — each with its own working tree. You can run a server on main while developing on a feature branch, without stashing or switching. This video uses visigit's branch mode to show all active worktrees alongside the branch topology.

#### Outline
| Time | Section |
|------|---------|
| 0:00 | The problem: you're mid-feature and need to test something on main |
| 1:00 | The old way: stash, switch, work, switch back, pop |
| 2:00 | `git worktree add ../hotfix-work hotfix/critical` — new directory, new checkout |
| 3:30 | Branch mode: both main and hotfix/critical shown; each has its own path label |
| 4:30 | Work in each directory independently — no stashing needed |
| 5:30 | `git worktree list` — all active worktrees with their paths |
| 6:30 | Branch mode updates as you commit in each worktree |
| 7:30 | `git worktree remove ../hotfix-work` — path disappears |
| 8:30 | `git worktree prune` — clean up stale entries |
| 9:30 | Constraint: same branch can't be checked out in two worktrees simultaneously |
| 10:30 | When worktrees shine: long-running builds, parallel reviews, CI environments |

#### Key Visual Moments
- Branch mode showing multiple branch nodes with their checked-out paths
- Topology updating as commits land in separate worktrees
- Worktree removal: branch node remains, path annotation gone

---

### EP 20 — Advanced — Force Push Is Destroying Someone's History: Here's the Proof

**visigit mode:** normal  
**Target length:** 11–13 min  
**Commands covered:** git push --force, git push --force-with-lease, git reflog (on remote)

#### YouTube Title
> git push --force Is Destroying Your Team's History — Watch It Happen in the Graph

#### YouTube Description
> Force push rewrites the remote ref to point at your local commit chain, discarding everything the remote had that you don't. If a teammate pushed after you last pulled, their commits are simply gone from the remote. This video makes the danger concrete by showing you exactly what the graph looks like before and after a force push — and why --force-with-lease is a safer alternative.

#### Outline
| Time | Section |
|------|---------|
| 0:00 | How force push looks safe from your local graph — and why it isn't |
| 1:00 | Build the scenario: you and a teammate both push to main |
| 2:00 | Teammate's commit: origin/main has advanced past your last fetch |
| 3:00 | `git push` fails: non-fast-forward rejection |
| 3:30 | The temptation: `git push --force` |
| 4:00 | Show what force push does: origin/main jumps to your commit; the teammate's commit is now unreachable from origin/main, though visigit still shows it via FETCH_HEAD (last fetched) |
| 5:00 | The teammate's commits are gone from the remote ref — locally still shown via FETCH_HEAD until your next fetch, and recoverable from their reflog |
| 6:00 | Safer alternative: `git push --force-with-lease` |
| 7:00 | force-with-lease: push fails if origin/main has moved since your last fetch |
| 8:00 | Legitimate uses of force push: rebased personal feature branches before PR merge |
| 9:00 | The rule: force push only to branches no one else has checked out |
| 10:00 | `--force-with-lease=refs/heads/main:<known-sha>`: the most surgical form |
| 11:30 | Recap: force push changes where a ref points; it does not delete objects (yet) |

#### Key Visual Moments
- Before force push: origin/main points to teammate's commit; your commit is behind
- After force push: origin/main jumps to your commit; the teammate's commit is orphaned from origin/main (still visible via FETCH_HEAD until the next fetch)
- force-with-lease rejection: no graph change because the push was blocked

---

## Tier 4 — Internals: Inside Git

---

### EP 21 — Internals — Inside a Commit: blob, tree, commit — Git's Four Object Types

**visigit mode:** verbose  
**Target length:** 13–15 min  
**Commands covered:** git commit (step-by-step observation)

#### YouTube Title
> Inside a git commit: blob, tree, commit Objects Explained with a Live Object Graph

#### YouTube Description
> Every git commit creates three types of objects: blobs (file contents), trees (directory listings), and a commit object (metadata + pointer to root tree). This video uses visigit's verbose mode to show you all three appearing in the graph the moment you run git commit — and explains the fourth object type (annotated tags) while it's fresh. By the end you'll understand exactly what git is storing on disk.

#### Outline
| Time | Section |
|------|---------|
| 0:00 | The premise: git is a content-addressable object store with a DAG on top |
| 1:00 | The four object types: blob, tree, commit, tag — brief overview |
| 2:00 | Start verbose monitor: `visigit --mode verbose --monitor` |
| 3:00 | `echo "hello" > hello.txt && git add hello.txt` — Staged Changes box appears |
| 4:00 | The blob object: file content hashed with SHA-1 (now SHA-256 capable) |
| 5:00 | `git commit -m "initial"` — three new nodes appear: commit → tree → blob |
| 6:30 | Walk through each node: what does each one store? |
| 7:30 | Add a second file: `src/core.py` in a subdirectory |
| 8:30 | Commit — root tree gets a child tree node for `src/`; child tree points to `core.py` blob |
| 9:30 | Each directory level is its own tree object with its own SHA |
| 10:30 | Commit object: parent SHA + tree SHA + author + committer + message |
| 12:00 | How this design enables fast branching: branches are just pointers to commit objects |
| 13:30 | Recap diagram: the full object graph for a two-file, two-directory, two-commit repo |

#### Key Visual Moments
- Staged Changes box appearing immediately on `git add`
- All three object types appearing simultaneously on `git commit`
- Child tree node for subdirectory below root tree
- Edge labels: "tree" from commit → root tree; filename labels from tree → blob

---

### EP 22 — Internals — Submodules vs Subtrees: Pointer or Merged Files?

**visigit mode:** verbose  
**Target length:** 12–14 min  
**Commands covered:** git submodule add, git subtree add

#### YouTube Title
> Submodules vs Subtrees: One Stores a Pointer, the Other Merges the Files — See the Difference

#### YouTube Description
> Two ways to include one repo inside another, and they couldn't be more different under the hood. A submodule stores a gitlink — a pointer to a specific commit in another repo — which visigit shows as a distinct node. A subtree merges the other repo's files directly into your tree as ordinary blobs, with its history as a second parent. This video opens both in verbose mode so you can see exactly what git stores in each case.

#### Outline
| Time | Section |
|------|---------|
| 0:00 | Same goal, opposite mechanics |
| 1:00 | `git submodule add ../lib lib` — what actually lands in your tree? |
| 2:00 | Verbose graph: a gitlink node (mode 160000) pointing at the submodule's commit |
| 3:00 | The .gitmodules file is a real blob; the submodule itself is just a pointer |
| 4:00 | Key point: your repo does NOT contain the submodule's files — only its SHA |
| 5:30 | Reset and try the other way: `git subtree add --prefix=vendor/lib ../lib main` |
| 6:30 | Verbose graph: the library's files appear as NORMAL blobs under vendor/lib |
| 7:30 | The subtree add is a MERGE commit — the library's history is a second parent |
| 8:30 | Content-addressable bonus: the imported tree is deduplicated in the graph |
| 9:30 | Trade-offs: submodule (light pointer, needs `submodule update`) vs subtree (self-contained) |
| 11:00 | Why visigit renders a gitlink distinctly but a subtree as plain objects |
| 13:00 | Recap: submodule = a SHA pointer node; subtree = the actual files + a merge |

#### Key Visual Moments
- Submodule: a distinct `gitlink` node pointing at another repo's commit, beside the .gitmodules blob
- Subtree: the imported files as ordinary blobs/trees under the prefix directory
- The subtree-add merge commit with two parents (your history + the imported history)
- Tree deduplication: the imported subtree sharing a tree node with the vendored copy

---

### EP 23 — Internals — Same File, Same SHA: How Git Never Stores the Same Content Twice

**visigit mode:** verbose  
**Target length:** 11–13 min  
**Commands covered:** git add, git commit (observing SHA reuse across commits)

#### YouTube Title
> Same File Content = Same SHA: How Git Avoids Storing Duplicates Across Commits

#### YouTube Description
> Every git object is identified by the SHA of its content. This means if you commit a file and don't change it, the next commit reuses exactly the same blob object — the same node in the graph. This video makes content-addressable storage visible by showing two commits in verbose mode sharing a blob node, and then showing what happens when you do change the file.

#### Outline
| Time | Section |
|------|---------|
| 0:00 | The claim: git doesn't copy files when you commit — it deduplicates |
| 1:00 | Create a repo with README.md and app.py; commit both |
| 2:00 | Verbose graph: commit 1 → tree → two blobs |
| 3:00 | Modify only app.py; `git commit -m "update app"` |
| 4:00 | Verbose graph: commit 2 → NEW tree → NEW blob for app.py + SAME blob for README.md |
| 5:30 | The README.md node: same SHA, same node, shared between both commits |
| 6:30 | Why: the blob SHA is a hash of the file content; same content = same hash |
| 7:30 | Consequence: renaming a file without changing its content reuses the same blob |
| 8:30 | Consequence: a file that appears in 1000 commits unchanged is stored exactly once |
| 9:30 | Trees are also deduplicated: if a subtree's contents don't change, its SHA doesn't change |
| 10:30 | When does duplication happen? Different content always = different SHA |
| 11:30 | Packfiles: git eventually delta-compresses similar blobs for network efficiency |

#### Key Visual Moments
- Two different commit nodes sharing the same README.md blob node (one blob, two inbound edges)
- New blob appearing for app.py with a different SHA after modification
- Tree node reuse: unchanged subtrees share the same tree SHA across commits

---

### EP 24 — Internals — The Staging Area Exposed: What git add Actually Does to the Object Store

**visigit mode:** verbose  
**Target length:** 12–14 min  
**Commands covered:** git add, git restore --staged, git rm --cached, git diff --staged

#### YouTube Title
> git add Creates a Blob Object Before You Even Commit — Watch It Appear in Verbose Mode

#### YouTube Description
> Most tutorials say "git add stages the file." What it actually does is compute the SHA of your file's content, write a blob object to .git/objects, and record the SHA in the index. The blob exists even before you commit. visigit's verbose mode makes this visible: the staged file appears in the graph with its blob SHA the moment you run git add — no commit required.

#### Outline
| Time | Section |
|------|---------|
| 0:00 | The index (staging area) is not just a list of files — it's a list of blob SHAs |
| 1:00 | Start fresh repo in verbose monitor mode |
| 2:00 | Create README.md; DO NOT run git add yet — Untracked box shows it |
| 3:00 | `git add README.md` — Staged Changes box appears with file name + blob SHA |
| 4:00 | The blob is already in `.git/objects` — the commit hasn't happened yet |
| 5:00 | `git commit` — Staged Changes disappears; commit + tree + blob chain appears |
| 6:00 | Edit README.md without staging: Unstaged Changes box appears with new SHA |
| 7:00 | Two SHAs visible: committed blob (in tree) vs working-tree blob (in Unstaged) |
| 8:00 | `git add README.md` again — Unstaged clears; Staged Changes shows new SHA |
| 9:00 | `git restore --staged README.md` — remove from staging, blob still in object store |
| 10:00 | `git rm --cached README.md` — remove from index but keep in working tree |
| 11:00 | `git diff --staged`: compares index blob SHAs to HEAD tree blob SHAs |
| 12:30 | Recap: add = write blob + update index; commit = write tree + write commit object |

#### Key Visual Moments
- Untracked box: file name only, no SHA (file not yet an object)
- Staged Changes box: file name + blob SHA (the blob object exists)
- Unstaged Changes box: modified tracked file with new SHA vs committed SHA
- All three boxes potentially visible simultaneously for different files

---

### EP 25 — Internals — All the Way Down: git cat-file, .git/objects, and Pack Files

**visigit mode:** verbose + terminal (git cat-file)  
**Target length:** 14–16 min  
**Commands covered:** git cat-file -p/-t/-s, git hash-object, ls .git/objects/, git gc, git verify-pack

#### YouTube Title
> What's Actually Inside .git/objects? Unpacking Blobs, Trees, and Commits with git cat-file

#### YouTube Description
> You've seen the object graph in visigit. Now let's open the objects themselves. git cat-file -p <sha> prints the raw content of any git object. In this video we crack open blobs, trees, and commits in the terminal alongside the verbose diagram — showing you exactly what bytes are stored on disk and how git's SHA hash is computed. We also explain how pack files compress thousands of loose objects into an efficient bundle.

#### Outline
| Time | Section |
|------|---------|
| 0:00 | Recap: we know the object types; now let's read the actual bytes |
| 1:00 | Build a two-commit repo; start verbose monitor alongside a terminal |
| 2:00 | `ls .git/objects/` — two-character prefix directories |
| 2:30 | A blob: `git cat-file -t <blob-sha>` (type) and `git cat-file -p <blob-sha>` (content) |
| 3:30 | Content is exactly the file content; SHA is SHA1("blob " + length + "\0" + content) |
| 4:30 | A tree: `git cat-file -p <tree-sha>` — mode + type + sha + filename per entry |
| 5:30 | Cross-reference with visigit verbose graph: tree entries match graph edges |
| 6:30 | A commit: `git cat-file -p <commit-sha>` — tree, parent, author, committer, message |
| 7:30 | `git hash-object --stdin`: compute SHA for any content |
| 8:30 | Verify: `echo "hello" | git hash-object --stdin` == blob SHA from earlier commit |
| 9:30 | `git gc` — loose objects become a pack file: `.git/objects/pack/*.pack` |
| 10:30 | `git verify-pack -v *.pack` — see every object in the pack with type and size |
| 11:30 | Delta compression: how pack files store object diffs instead of full content |
| 13:00 | The full picture: git is just a key-value store + a DAG + some ref pointers |
| 14:30 | What to explore next: git's protocol, shallow clones, partial clones |

#### Key Visual Moments
- Verbose graph SHA labels matching the SHAs shown in `git cat-file` terminal output
- The identical blob SHA appearing in both the graph node and `ls .git/objects/` output
- Pack file creation: loose object files disappear from `.git/objects/`; pack file appears

---

## Integration Test Notes

Three companion test layers keep every lesson diagram accurate:

- [tests/test_lessons.py](../tests/test_lessons.py) — **key** node/edge presence per episode
  (survives cosmetic layout changes).
- [tests/test_lessons_full.py](../tests/test_lessons_full.py) — **exhaustive** per-step checks:
  the exact, complete node + edge + label set for each lesson state, hand-derived from git
  semantics. An autouse fixture also cross-checks every step against the independent oracle.
- [tests/git_oracle.py](../tests/git_oracle.py) + [tests/test_oracle_differential.py](../tests/test_oracle_differential.py)
  — an **independent** oracle that re-derives the expected graph straight from `git` plumbing
  (a different algorithm) and is compared against visigit over fixed scenarios and randomly
  generated repos, in normal / verbose / branch modes (including bare "origin" repos).

Running them:
```bash
pytest tests/test_lessons.py tests/test_lessons_full.py tests/test_oracle_differential.py -v
```

When a test fails it almost always means a visigit bug would make the diagram in that lesson
wrong. Git behaviour varies across versions (e.g. auto-creating `refs/remotes/origin/HEAD`),
so the CI matrix runs the suite on multiple OS and Python versions; record lessons on a recent
stable git and state the version on-screen.
