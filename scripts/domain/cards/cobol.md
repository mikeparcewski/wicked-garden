# Language card: COBOL / JCL / BMS (CardDemo family)

Applies to extensions: .cbl .CBL .cob .cpy .CPY .jcl .JCL .prc .PRC .proc .bms .csd .ctl .ddl .dcl .ca7 .controlm

## comment syntax
- fixed-form COBOL: column 7 is `*` or `/` -> comment line. Free-form: a line whose first non-blank is `*>`.
- JCL: a line starting `//*` is a comment.
- BMS / assembler macro: a line whose column 1 is `*` is a comment.

## declaration patterns (a range made only of these lines is dropped from the unidentified list)
- `^\s*COPY\s` , `^\s*EXEC\s+SQL\s+INCLUDE\b`
- `^\s*(IDENTIFICATION|ID|ENVIRONMENT|DATA|PROCEDURE)\s+DIVISION\b`
- `^\s*[A-Z0-9-]+\s+SECTION\.\s*$` (only outside the PROCEDURE DIVISION)
- `^\s*(PROGRAM-ID|AUTHOR|DATE-WRITTEN|DATE-COMPILED|INSTALLATION|SECURITY|SOURCE-COMPUTER|OBJECT-COMPUTER|SPECIAL-NAMES|FILE-CONTROL|INPUT-OUTPUT|CONFIGURATION|WORKING-STORAGE|LINKAGE|LOCAL-STORAGE|FILE)\b`
- `^\s*(SELECT|ASSIGN|ORGANIZATION|ACCESS|RECORD\s+KEY|ALTERNATE|FILE\s+STATUS|FD|SD|RECORDING|BLOCK|LABEL)\b`
- `^\s*\d{1,2}\s+\S` (data description entries: level numbers) and continuation lines of a data entry (`VALUE`, `PIC`, `OCCURS`, `REDEFINES`)
- `^\s*(EXIT|GOBACK)\s*\.?\s*$`

## definition-looking regex (a line matching it with no node starting there becomes a range start)
- PROCEDURE DIVISION paragraph or section header, after removing columns 1-7 (fixed form):
  `^[A-Z0-9][A-Z0-9-]*(\s+SECTION)?\.\s*$` where the name is not a COBOL verb or `END-*`.
- JCL step: `^//([A-Z0-9@#$]{1,8})\s+EXEC\b`
- BMS: `^([A-Z0-9@#$]+)\s+DFHM(SD|DI|DF)\b`

## structural splitter
- COBOL PROCEDURE DIVISION: paragraph header to the next paragraph header.
- JCL: `EXEC` step to the next `EXEC` step (the step's DD and inline `*`/`DD *` control cards belong to the step).
- BMS: `DFHMDI` map to the next `DFHMDI`; inside a map, `DFHMDF` field to the next field.
- CSD: `DEFINE` to the next `DEFINE`.

## decision tokens (M7: a not_rule whose lines contain one goes to the validator)
`IF`, `ELSE`, `EVALUATE`, `WHEN`, `PERFORM ... UNTIL`, `PERFORM ... VARYING`, `AT END`, `NOT AT END`, `INVALID KEY`,
`NOT INVALID KEY`, `ON SIZE ERROR`, `ON OVERFLOW`, `GO TO ... DEPENDING`, `NEXT SENTENCE`, `SEARCH`, `SET <88-name> TO TRUE`,
`CALL 'CEE3ABD'`, `ABEND`, a file-status comparison (`'00'`, `'10'`, `'23'` ...), JCL `COND=`, `IF ... THEN`, SORT `INCLUDE COND`/`OMIT COND`.
Record updates are refused in a not_rule too: `WRITE`, `REWRITE` or `DELETE` of a record, or a `PERFORM` of a paragraph that does one. State them (rule 11).

## call-site greps (trigger fetch)
`PERFORM X`, `PERFORM X THRU Y`, `GO TO X`, `CALL 'X'`, `CALL X`, `EXEC CICS LINK PROGRAM('X')`, `EXEC CICS XCTL PROGRAM('X')`, JCL `EXEC PGM=X`.

## scan patterns (entry points and config, §3.1 A)
- JCL job step: `^//(\S+)\s+EXEC\s+PGM=([A-Z0-9@#$]+)` -> entry {kind: job, name: <member>/<step>, handler program}; a step running a proc: `^//(\S+)\s+EXEC\s+(PROC=)?([A-Z0-9@#$]+)\b` resolved against `*.prc`/`*.proc` members.
- JCL config: `^//(\S+)\s+DD\b` with a following `DSN=([^,\s)]+)` (same or continuation line) -> config key DD name + dataset; inline control cards: `DD *` up to `/*`; `SYSIN DD` members.
- CICS transaction: in `*.csd`, `DEFINE TRANSACTION(T)` ... `PROGRAM(P)` within the same DEFINE block -> entry {kind: transaction, name: T, handler P}.
- CICS file config: `DEFINE FILE(F)` ... `DSNAME(D)` -> config key F + dataset.
- Screens: BMS map sets (`DFHMSD`) and maps (`DFHMDI`); programs that `SEND MAP`/`RECEIVE MAP` them (estate program->map edges).
- Schedulers: `*.ca7`, `*.controlm` by text (job names).
- Config read by a program: `SELECT f ASSIGN TO DD` (the DD name binds the program to the step's DD statements).

## semantics the model must get right (the 13 B1 traps, E§3b)
1. `NEXT SENTENCE` transfers control to the statement after the next separator period. It does NOT end a PERFORM loop and it skips everything up to that period, including any `ELSE` branch and statements after `END-IF` within the same sentence.
2. `PERFORM A THRU B` runs every paragraph physically between A and B, in source order. A plain `PERFORM A` runs only A.
3. A paragraph holding only `EXIT.` does nothing; `GO TO X` transfers without returning.
4. `EVALUATE`: the first WHEN that is true wins; consecutive `WHEN` lines with no statement between them share the next statement (an OR). `WHEN OTHER` is the default.
5. 88-level condition names: `IF FLAG-NAME` tests the parent field against the 88's VALUE list; `SET FLAG-NAME TO TRUE` moves that value.
6. `INVALID KEY` / `AT END` / `NOT INVALID KEY` branches run only on that I/O outcome. File status `'00'` success, `'10'` end of file, `'23'` record not found, `'02'` duplicate alternate key.
7. An `IF` without a period inside an outer `IF` nests; a period ends ALL open IFs.
8. A branch can be unable to run (for example an EOF update placed after the loop's exit test sets the EOF flag). Read the loop condition before stating what happens at end of file. State such a branch as the code writes it, and say in a concern that it cannot run, citing the test that prevents it.
9. `PERFORM UNTIL c` tests c before each iteration (TEST BEFORE is the default).
10. `AND`/`OR` precedence: `AND` binds tighter; `NOT` applies to the next condition only.
11. Comparisons are exact: `> 500` is not `>= 500`.
12. `MOVE` into a shorter alphanumeric field truncates on the right; into a numeric field it aligns on the decimal point and truncates high-order digits.
13. An abend routine (`CALL 'CEE3ABD'`, `9999-ABEND-PROGRAM`) ends the job; code after it in the same path does not run.

## platform facts (shown to the checker with every statement; DES-j6-v2 §1)
CARD FACTS (COBOL / IBM LE): CALL 'CEE3ABD' abends the job and does not return. CICS RETURN with TRANSID schedules that transaction for the next input. XCTL transfers control and does not return.
