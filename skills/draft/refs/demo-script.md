# Kind: demo script

A script a presenter follows to show working software live: what to click, what to say, what the
audience sees. It is a document to read, not a recording (a recording is the Demo video card). The
brief's `Kind: demo script.` line selects this ref. The skill's three floors still apply.

## Shape

1. **Audience and goal:** who is watching and the one thing they should believe at the end.
2. **Setup checklist:** environment, the URL or command that starts the app, test data, accounts by
   role (never a password or token), browser state to reset. Each item is something a presenter can
   check off.
3. **Run of show,** a table with one row per beat:

   | Time | Action (what to click or type) | Say | They see |
   |---|---|---|---|

   The times add up to the brief's length. With no length given, aim for five minutes and say so in
   the notes.
4. **Fallbacks:** for each risky beat, what to say and do if it fails (a prepared screenshot, a
   second path, moving on).
5. **The close:** the line that restates the goal, and the ask.

## Rules

- **Only what exists.** Every beat shows a feature the repository has: cite the route, the
  component or the command (`data-source`) for each action. A planned feature is said as planned,
  never demonstrated as live.
- **Real actions.** Name the exact button, menu item, field and input value, as the code or the
  running app spells them. Do not paraphrase a label.
- **One path.** The happy path, with the fallbacks beside it. Branches belong in a second script.
- **Say lines are spoken:** short sentences, no reading of the screen aloud.
- **Sized:** no page budget unless the brief names one (self-check `--no-pages`); the time budget
  is the run of show's total.

## Never

- script a feature, a number or a screen the sources do not show;
- include a credential, a personal email or production data in setup or actions;
- promise a time the beats do not add up to.
