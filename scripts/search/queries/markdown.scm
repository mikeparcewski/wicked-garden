; Markdown tree-sitter queries for extracting code symbols and relationships
; Converted from markdown-tags.scm

; Markdown query patterns

; H1 headers
(atx_heading
  (atx_h1_marker)
  (inline) @code_function.name) @code_function.def

; H2 headers
(atx_heading
  (atx_h2_marker)
  (inline) @code_function.name) @code_function.def

; H3 headers
(atx_heading
  (atx_h3_marker)
  (inline) @code_function.name) @code_function.def

; H4 headers
(atx_heading
  (atx_h4_marker)
  (inline) @code_function.name) @code_function.def

; H5 headers
(atx_heading
  (atx_h5_marker)
  (inline) @code_function.name) @code_function.def

; H6 headers
(atx_heading
  (atx_h6_marker)
  (inline) @code_function.name) @code_function.def

; Code blocks with language specified
(fenced_code_block
  (info_string
    (language) @name.codeblock.language)) @codeblock

; Sections (implicit from headers)
(section) @section
