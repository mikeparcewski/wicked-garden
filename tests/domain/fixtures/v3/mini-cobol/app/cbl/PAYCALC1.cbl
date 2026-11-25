       IDENTIFICATION DIVISION.
       PROGRAM-ID. PAYCALC1.
       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT PAY-FILE ASSIGN TO INFILE.
       DATA DIVISION.
       FILE SECTION.
       FD  PAY-FILE.
       01  PAY-LINE                PIC X(80).
       WORKING-STORAGE SECTION.
       COPY PAYREC.
       01  WS-EOF                  PIC X VALUE 'N'.
       PROCEDURE DIVISION.
       MAIN-PARA.
           OPEN INPUT PAY-FILE
           PERFORM READ-PARA UNTIL WS-EOF = 'Y'
           CLOSE PAY-FILE
           GOBACK.
       READ-PARA.
           READ PAY-FILE INTO PAY-RECORD
               AT END MOVE 'Y' TO WS-EOF
           END-READ
           IF PAY-HOURS > 40
               COMPUTE PAY-AMOUNT = PAY-RATE * 40
                   + PAY-RATE * 1.5 * (PAY-HOURS - 40)
           ELSE
               COMPUTE PAY-AMOUNT = PAY-RATE * PAY-HOURS
           END-IF.
