# Storytelling: chapters, captions, claims

## Chapter design

Each chapter answers one question the audience has, with one case, in a few minutes.

- **One capability per chapter.** If a chapter shows two things, split it or cut one.
- **Open with the problem**, in the customer's words where possible ("He typed the ESNs in by hand, please double
  check them"). Then the action, then the result, then why it matters.
- **End on evidence.** A cited finding, a passed check, an audit entry: something the audience can verify on screen.
- **Self-contained.** Starts from a known page, uses its own cases, resets what it touches. Then chapters can be
  reordered, dropped for a short path, or re-recorded alone.
- **Read-only when possible.** Tours of a library, a history, a dashboard or search need no reset and never fail.

## Ordering

Go from familiar to impressive to trustworthy:

1. **Triage**: the landing page as a ranked to-do list.
2. **Core flow end to end**: one clean case all the way to done, including the human approval steps.
3. **Hard cases**: messy input, missing information, conflicts, uploads that change the outcome.
4. **Learning and governance**: new knowledge captured once, reviewed by a second person, reused only where it applies.
5. **Knowledge and trust**: where the rules live, how checks are built from them, how a result links back to its rule.
6. **360 view**: everything about one customer, with an assistant that reads it.
7. **Wrap-up**: the audit trail and the measured numbers.

Put the most fragile live step early in a live session (energy is high, time is available) or pre-bake it.
Keep a **short path** (about a quarter of the length) that skips the deep dives.

## Chapter metadata (for slides and video)

For every chapter write:

- **Key**: `NN-slug` (`03-messy-input`), stable, used for files and re-recording.
- **Title**: 2-6 words, sentence case ("A hand-typed ESN list").
- **Blurb**: one sentence that states what the chapter proves, not what it clicks.
- **Tags**: 2-5 capability chips ("Extraction with sources", "Human gates", "Search").
- **Resets**: the cases it changes.

## Captions and voice

Captions (and presenter lines) follow the same pattern:

- **Kicker**: 1-3 words naming the beat ("Result", "Governance", "Upload").
- **Title**: one plain sentence, the takeaway ("Nothing needs attention: the unit actions reconcile").
- **Body**: optional, one or two lines of why or how; emphasise the key phrase.

Rules:

- Say what the audience should notice, in their words, not the UI's internals. No internal keys or code names.
- Present tense, active voice, short sentences. One idea per caption.
- The caption changes **with** the picture, not after it: introduce the next screen just before navigating to it.
- Give readers time: roughly 40 ms per character, 2.5 s minimum.

## Honest claims

- Numbers on screen or in the script are **measured** (say where) or labelled **estimate**. Never mix them.
- Name simulated systems and synthetic data out loud, once, early.
- Don't claim the model "knows" something the system checks deterministically; say which part is a rule in code and
  which part is the model reading or explaining.
- Show the guardrail every time you show automation: who approved, what was refused, what was not applied and why.
- If a result varies between runs, say so in the script's recovery tips rather than hoping it won't.
