## Plan: replace moment with date-fns

```
mechanical-first:
  inventory: ast-grep run -p 'moment($$$)' -l ts src | wc -l
  count: 212
  recipe_checked: npm search moment codemod — none maintained; jscodeshift moment-to-date-fns transform — covers format/add/diff
  codemod: jscodeshift -t moment-to-date-fns.js src (self-flagged 9 sites: locale-dependent parsing)
  gate: npm test && npx tsc --noEmit
  residue: 9
```

Then hand-edit the 9 flagged sites and run the gate.
