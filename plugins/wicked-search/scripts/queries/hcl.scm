; HCL (Terraform) tree-sitter queries for extracting code symbols and relationships

; All blocks with a name (resource, variable, output, module, data, provider)
; Extract the name from the string_lit
(block
  (identifier) @_block_type
  (string_lit (template_literal) @code_variable.name)
) @code_variable.def

; Resource blocks have two string_lits: type and name
; resource "aws_instance" "example" { ... }
(block
  (identifier) @_block_type
  (string_lit) @_resource_type
  (string_lit (template_literal) @code_variable.name)
  (#eq? @_block_type "resource")
) @code_variable.def

; Data blocks have two string_lits: type and name
; data "aws_ami" "example" { ... }
(block
  (identifier) @_block_type
  (string_lit) @_data_type
  (string_lit (template_literal) @code_variable.name)
  (#eq? @_block_type "data")
) @code_variable.def

; Comments
(comment) @comment
