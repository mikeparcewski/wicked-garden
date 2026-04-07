; Perl tree-sitter queries for extracting code symbols and relationships
; Converted from perl-tags.scm

; Perl query for legacy systems

; Subroutine definitions
(subroutine_declaration_statement
  name: (bareword) @code_function.name) @code_function.def

; Package declarations
(package_statement
  (package) @package.name)

; Use statements (imports)
(use_statement
  (package) @import)
