# release — prepare a release pull request

The `release` action of `wicked-garden-engineering`, and the build step of wicked-crew's `release`
workflow (the **Prepare a release** card). The readiness verdict (GO / CONDITIONAL / NO-GO) comes
from the step before this one (`wicked-garden-qe-release-readiness-engineer`). This ref covers the
change itself: versions bumped, the changelog cut from what merged, and a release record that the
fidelity check reads.

## What it delivers, and what it never does

A release pull request, and nothing else:

- the version bumped in every file that carries it;
- the changelog cut from what merged since the last release, each entry tracing to a merged change;
- the release record (below) in your output and the pull request body.

**Never** tag, push a tag, publish (npm, crates.io, PyPI, a container registry), create a hosted
release, or merge. Those stay with people. If the repository's release script tags or publishes, do
not run it: make the file edits it would make, and run only a step that writes nothing outside the
tree. A request to "tag it when you're done" or "publish it" is answered, not obeyed: say that a
release pull request is the whole of this job.

**Never** change behaviour in a release pull request. A defect you find is a finding for a Bug
job, not a fix here.

## If the readiness verdict says NO-GO

Do not prepare the release. Report the blockers the verdict named and stop. On CONDITIONAL,
prepare it and copy each condition into the record and the pull request body.

## Steps

1. **The last release: its version and its boundary commit,** recorded apart.
   - **Tag first.** Find the repository's release-tag convention for the package being released
     (`v1.4.2`, or `<package>-v1.4.2` in a repository that releases several packages) from its
     existing tags and changelog link references. Take the highest tag of that convention merged
     into HEAD (`git tag --list 'v*' --merged HEAD --sort=-v:refname`, with the convention's
     pattern). Never take a tag of another package, a milestone or a pre-release you are not
     releasing from. The tag's commit is the boundary.
   - **No matching tag, but a released changelog heading** (`## [1.4.2]`): that is the previous
     version. Its boundary is the commit that added the heading
     (`git log -1 --format=%H -S'## [1.4.2]' -- CHANGELOG.md`; a heading is added once and never
     removed, so the newest match is the one that added it). Check it with `git show <sha>`.
   - **Neither: a first release.** No previous release is recorded. The manifest's version (or the
     person's) is the version to release, not a previous one; there is no boundary, and the range is
     the whole history.
   - Say which source you used. If the sources disagree, use the tag and record the disagreement as
     a finding. If a previous release is recorded but its boundary cannot be found, stop and report
     it rather than guess a range.
2. **The range.** `git log --first-parent --format='%H %s' <boundary>..HEAD` lists what merged
   (for a first release, `git log --first-parent --format='%H %s' HEAD`). Take each change's pull
   request number from its subject (`(#123)`) where the repository squashes or merges through pull
   requests.
3. **The bump.** An explicit version in the person's words wins, and a first release keeps the
   manifest's version unless the person names one. Otherwise derive it from the range and name the
   evidence:
   - a breaking change (a `BREAKING CHANGE` footer, a `!` subject, a removed or renamed public
     API, a raised minimum runtime) → major, or minor while the version is `0.x`;
   - any new feature → minor;
   - fixes, docs and chores only → patch.
4. **Every version-carrying file.** Search the old version across the tree
   (`git grep -n -F '<old version>'`) and judge each hit. Manifests and their lockfiles
   (`package.json` with `package-lock.json`, `Cargo.toml` with `Cargo.lock`, `pyproject.toml`,
   a `__version__`, plugin manifests, chart files) change. History stays: older changelog
   sections, migration notes, pinned examples of past versions. In a workspace, bump only the
   packages being released, plus the internal pins that name them.
5. **Lockfiles.** Re-stamp them with the package manager in its lockfile-only mode where it has
   one (`npm install --package-lock-only --ignore-scripts`, `cargo update --workspace --offline`),
   so the tool writes the version line, not you. Never let a lockfile step run the repository's
   lifecycle scripts: a `prepare` or `postinstall` hook may tag, publish or write. If the tool is not on this seat, say so in the
   record; do not hand-edit a lockfile beyond the version entries.
6. **The changelog.** Follow the file's own format; add no style of your own.
   - In the Keep a Changelog shape: move the `[Unreleased]` entries under
     `## [X.Y.Z] — YYYY-MM-DD` and leave an empty `[Unreleased]` above it.
   - Link references, when the file uses them: build each ref with the tag convention from step 1
     (`v1.5.0`, or `<package>-v1.5.0`). The new version compares from the previous release's tag,
     or from the boundary commit when that release has no tag; a first release links to its own
     tag instead of a comparison. Retarget `[Unreleased]` to compare from the new version's tag.
   - A merged change in the range with no entry: add one under the right subsection, citing its
     pull request or commit. If the repository's convention leaves out chores or CI-only changes,
     list those as "omitted by convention" in the record instead.
   - An entry that matches nothing in the range: keep it, and flag it in the record. The fidelity
     check decides; you do not delete someone's entry.
   - Never rewrite a released section.
7. **Check the diff.** `git diff --stat` touches only version files, lockfiles and the changelog
   (and release notes, when the repository keeps them apart). Any other file in the diff is a
   defect unless it carries the version string. Run the repository's own build and test command
   once as a smoke; the test step runs them again.

## The release record (your output)

The critique step checks the changelog against the merged history from this record, both ways:
every entry traces to a change in the range, and every change in the range has an entry or a stated
reason for leaving it out. Write it exactly in this shape:

```
RELEASE vPREV -> vX.Y.Z (bump: minor — 3 features, 0 breaking; source of vPREV: tag)
                         (a first release: RELEASE (first) -> vX.Y.Z, RANGE: whole history)
RANGE <boundary sha>..<head sha>: 14 merged changes (boundary: tag v1.4.2)
VERSION FILES: package.json:3 (1.4.2 -> 1.5.0); package-lock.json:3,9 (re-stamped by npm)
CHANGELOG: 12 entries, each with its PR or commit; added: #412, #415; flagged: "faster search" (no change in range)
OMITTED BY CONVENTION: #409 (ci), #411 (chore)
READINESS: CONDITIONAL — "quarantine the two auth flakes" (copied from the readiness step)
NOT DONE (people do these): tag vX.Y.Z, publish, hosted release
```

Quote the readiness verdict; never restate it in your own words. If a step could not run on this
seat (no package manager, no network for a compare URL), the record says which and why.
