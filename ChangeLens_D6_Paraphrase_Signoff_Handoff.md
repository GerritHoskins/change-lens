# Handoff: D-6 paraphrase sign-off

**Repo:** `C:\Users\Gerrit\job-search\POCs\change-lens` (branch `main`, remote https://github.com/GerritHoskins/change-lens). At handoff, `main` is at `2e8eb15` and level with `origin/main`. The untracked `.claude-flow/` folder is not ours; leave it alone.

**Goal:** close the last text-side D-6 step recorded in `docs/06-decision-log.md`: "the owner signs off every paraphrase in `scripts/eval/bases.py` (07 §3)".

## Who decides

The owner (the user) decides. You do not.

`docs/07-eval-dataset.md` §3 says a language model may draft texts but never writes gold labels, and every drafted text is read by a person. So you must not approve, reject or rewrite a paraphrase on your own judgement. Your job:

1. Present the 24 pairs below to the owner, with the flagged concerns.
2. Collect a verdict per pair: ok, or the replacement wording the owner chooses.
3. Apply exactly those verdicts, test, regenerate, record and commit.

If the owner says "you choose" for a flagged pair, offer a concrete wording and get an explicit yes before applying it.

## Background

- `scripts/eval/bases.py` holds 3 base briefs (B-001, B-002, B-003) with 24 items.
- Each item renders the original sentence `tpl` and the reworded sentence `para`, with the item's value substituted for `{v}`.
- The `rewording` operator in `scripts/eval/generate.py` swaps `tpl` for `para` and labels the result `equivalent`, not material. A paraphrase that changes meaning therefore produces a wrong gold label.
- The pass criteria come from 07 §4, under "Approval wording". A pair passes only if all four of these hold:
  1. **Same actor:** the same party does the work or holds the responsibility.
  2. **Same required action.**
  3. **Same binding force:** "must" ≠ "should", "only after" ≠ "after", "capped" ≠ "estimated", "including VAT" ≠ "excluding VAT".
  4. **Nothing added or dropped:** for example, a fixed date must not become a "no later than" window, and a budget must not become a cost.

## The 24 pairs

The pairs are shown with each item's default value `v`. ⚠ marks a concern raised by the previous agent; the owner decides.

| # | Item | `tpl` | `para` |
|---|---|---|---|
| 1 | B-001 pages | Design 8 page templates for the new website. | The new website needs 8 page templates designed. |
| 2 | B-001 format | All icons must be delivered as SVG files. | Every icon must be handed over as SVG files. |
| 3 | B-001 tone | The visual style of the designs is warm and playful. | The designs have a warm and playful visual style. |
| 4 | B-001 review | First design review on 14 March 2027. | The first review of the designs takes place on 14 March 2027. |
| 5 ⚠ | B-001 final | Final files are due on 30 April 2027. | The final files must reach us by 30 April 2027. |
| 6 | B-001 budget | The total budget is EUR 18,000, including VAT. | Including VAT, the budget comes to EUR 18,000 in total. |
| 7 | B-001 copy | Website copy is written by Contact A. | Contact A writes the copy for the website. |
| 8 | B-001 approval | Each milestone is complete when the client signs it off in writing. | A milestone counts as complete once the client signs it off in writing. |
| 9 | B-002 pages | Lay out a printed brochure of 24 pages. | The printed brochure runs to 24 pages and needs laying out. |
| 10 ⚠ | B-002 print | Artwork must be supplied as print-ready PDF/X-4. | The artwork must come as print-ready PDF/X-4. |
| 11 | B-002 photos | Retouch 15 campus photographs. | 15 photographs of the campus need retouching. |
| 12 | B-002 draft | The first draft is due on 2 February 2027. | The first draft must be delivered on 2 February 2027. |
| 13 | B-002 print_date | Files go to the printer on 1 March 2027. | On 1 March 2027 the files are sent to the printer. |
| 14 | B-002 fee | The fixed fee is GBP 6,400, excluding VAT. | Excluding VAT, the fee is fixed at GBP 6,400. |
| 15 | B-002 photo_owner | Photography is organised by Contact C. | Contact C organises the photography. |
| 16 | B-002 signoff | Printing starts only after the Head of Marketing approves the proof. | Printing begins only after the Head of Marketing approves the proof. |
| 17 | B-003 videos | Produce 3 short videos for social media. | 3 short social media videos are to be produced. |
| 18 | B-003 res | Each video must be exported in 1080p. | Every video must be exported in 1080p. |
| 19 ⚠ | B-003 length | No video may be longer than 30 seconds. | The maximum length of any video is 30 seconds. |
| 20 | B-003 shoot | Filming takes place on 10 June 2027. | The shoot is on 10 June 2027. |
| 21 | B-003 launch | The campaign launches on 1 July 2027. | Launch of the campaign is set for 1 July 2027. |
| 22 ⚠ | B-003 budget | The production budget is capped at EUR 9,500. | Production costs are capped at EUR 9,500. |
| 23 | B-003 music | Music licensing is handled by Contact E. | Contact E takes care of music licensing. |
| 24 ⚠ | B-003 approval | Videos are published after the trustees sign off the final cut. | Publication follows once the trustees sign off the final cut. |

Why each ⚠ pair was flagged:

- **5:** "due on" becomes "must reach us by". That turns a fixed date into a window and adds delivery to the client. Candidate fix: `"The final files must be delivered on {v}."`
- **10:** "supplied" implies who delivers the artwork; "come as" does not. Candidate fix: `"The artwork must be supplied as {v}."`
- **19:** a prohibition ("may not be longer") becomes a description ("the maximum length is"). Candidate fix: `"No video may run longer than {v}."` Keep the word "may", because the item's flip is `["may", "should"]`.
- **22:** a budget cap becomes a cost cap. Candidate fix: `"The budget for production is capped at {v}."`
- **24:** "follows once" can read as publication happening automatically. Candidate fix: `"Videos go live only after {v}."` This is not equivalent either: it adds "only". Check it with the owner, or use `"Videos are released after {v}."`

## Steps

### 1. Collect the owner's verdicts

Collect a verdict for all 24 pairs. Accept a compact reply, for example "all ok except 5 → X, 22 → Y". Do not proceed with any pair missing.

### 2. Edit `scripts/eval/bases.py`

Read the file first, then use the Edit tool.

- Change only the `"para":` string of the affected items. Never touch `tpl`, `v`, `alts`, `vague`, `flip`, `id` or `cat`.
- Each `para` must contain `{v}` exactly once.
- Keep every binding word that appears in the item's `tpl`: must, only, capped, including, excluding. The test `test_paraphrases_keep_binding_words` enforces this.

### 3. Update the golden digest

This step applies only if any `para` changed. Run this from the repo root in Git Bash:

```bash
python -I -c "import sys,hashlib,json; sys.path.insert(0,'scripts/eval'); import generate; h=hashlib.sha256(); [h.update(json.dumps(r,sort_keys=True).encode()) for r,_,_ in generate.generate(per_op=6,seed=7)]; print(h.hexdigest())"
```

The current value is `4852dad289bfb579bcef8bfb1548ec0ec3c65a94450d2f7c35e3f108457574d9`. With no edits, the command must print that same value. Put the new value into `GOLDEN = "..."` in `scripts/eval/test_generate.py`, at line 20.

### 4. Test

Run both commands:

```bash
python -m unittest discover -s scripts/eval
powershell -File scripts/ci.ps1
```

- The unit tests must report 27 tests and OK.
- CI must end with `CI PASS`.

Do not weaken a test to make it pass. If a binding-word test fails, the wording is wrong; go back to the owner.

### 5. Regenerate the private constructed set

This step applies only if any `para` changed. The output lives outside git and is overwritten in place. The generator refuses to write inside a git tree.

```bash
python scripts/eval/generate.py --out ../change-lens-data/constructed --per-op 6 --seed 7 --start 500
python scripts/eval/validate.py --records ../change-lens-data/constructed/records.jsonl
```

The second command must print `PASS: 66 records, 0 errors`.

### 6. Record the sign-off

Append a row to the end of the table in `docs/06-decision-log.md`. Its columns are date | decision | source. Use today's date and list the changed items, or write "none":

```
| <YYYY-MM-DD> | D-6 paraphrases signed off by the owner: all 24 in `scripts/eval/bases.py` checked against 07 §4 (actor, action, binding force kept). Changed: <items, or none> | Owner |
```

Optionally, append a note to the GR-5 row in `docs/review-ledger.md` saying that the owner sign-off is done.

### 7. Commit

```bash
git add scripts/eval/bases.py scripts/eval/test_generate.py docs/06-decision-log.md docs/review-ledger.md ChangeLens_D6_Paraphrase_Signoff_Handoff.md
git commit -m "Sign off the D-6 paraphrases"
```

- No `Co-Authored-By` trailer; `job-search/CLAUDE.md` forbids it, even if the tool suggests one.
- Do not stage `.claude-flow/`, `__pycache__/` or any generated texts.

### 8. Push

Push only after the owner explicitly says so:

```bash
git push origin main
```

## Constraints

- Real client data and source documents never go into git.
- Keep every file under 500 lines.
- One writer in this worktree at a time.
- Do not start the other open D-6 items: the PDF and image operators, labelling the 26 real pairs, and the UK rescan. They are separate tasks.

## Done when

All of these hold:

- All 24 pairs have an owner verdict.
- The edits are applied.
- The unit tests and CI pass.
- `validate.py` passes on the regenerated set, if any `para` changed.
- The 06 row is added.
- The commit is made.

Report back with:

- the verdict list;
- the commit hash;
- the last lines of the test, CI and validate output.
