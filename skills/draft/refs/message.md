# Kind: message

A short message for one channel: an email, a chat post, an announcement, a reply. The brief's
`Kind: message.` line selects this ref. The skill's three floors still apply; a message is a screen
deliverable with no page budget.

## Shape

1. **Subject or first line:** the point in under ten words (for chat, the first line is the subject).
2. **The ask or the news** in the first sentence: what you want the reader to do, by when, or what
   changed for them.
3. **Context:** two to four sentences, each fact cited (a link to the pull request, the run, the
   document).
4. **The ask again,** with its date, when there is one. One ask per message.
5. **Sign-off** in the channel's convention.

## Rules

- **Short:** under 150 words unless the brief asks for more. Cut context before the ask.
- **The channel sets the tone.** Chat: plain, no greeting block, a list only for three or more
  items. Email: a greeting and a sign-off. An announcement: what changes, for whom, from when, and
  where to ask.
- **Links are cited claims.** Each one goes to the source the claim comes from, written out or as
  link text that says where it goes ("the release pull request"), never "here".
- **Unknown recipient:** write without a name rather than a `[Name]` placeholder; the floor fails a
  placeholder.
- **Self-check:** `--no-pages --min-font-pt 0 --mode screen`.

## Never

- send, post or schedule it: this is a draft for a person to send;
- promise a date, a fix or a commitment the sources do not show;
- put a credential, a private address or internal-only detail in a message meant for outside readers.
