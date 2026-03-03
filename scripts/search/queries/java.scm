; Java tree-sitter queries for extracting code symbols and relationships
; Enhanced for Spring/JPA annotation detection

; ============================================================================
; Class declarations with annotations
; ============================================================================

; Class with annotations (captures @Entity, @Controller, @Service, @Table, etc.)
(class_declaration
  (modifiers
    (marker_annotation
      name: (identifier) @code_class.annotation
    )?
    (annotation
      name: (identifier) @code_class.annotation
      arguments: (annotation_argument_list
        (element_value_pair
          key: (identifier) @code_class.annotation_key
          value: (_) @code_class.annotation_value
        )?
        (string_literal)? @code_class.annotation_default
      )?
    )?
  )?
  name: (identifier) @code_class.name
  superclass: (superclass
    (type_identifier) @code_class.bases
  )?
  interfaces: (super_interfaces
    (type_list
      (type_identifier) @code_class.bases
    )
  )?
  body: (class_body) @code_class.body
) @code_class.def

; Interface declarations
(interface_declaration
  name: (identifier) @code_interface.name
  body: (interface_body) @code_interface.body
) @code_interface.def

; ============================================================================
; Method declarations with annotations
; ============================================================================

; Method with annotations (captures @RequestMapping, @GetMapping, etc.)
(method_declaration
  (modifiers
    (marker_annotation
      name: (identifier) @code_method.annotation
    )?
    (annotation
      name: (identifier) @code_method.annotation
      arguments: (annotation_argument_list
        (element_value_pair
          key: (identifier) @code_method.annotation_key
          value: (_) @code_method.annotation_value
        )?
        (string_literal)? @code_method.annotation_value
      )?
    )?
  )?
  type: (_) @code_method.return_type
  name: (identifier) @code_method.name
  parameters: (formal_parameters) @code_method.params
  body: (block)? @code_method.body
) @code_method.def

; Constructor declarations
(constructor_declaration
  name: (identifier) @code_method.name
  parameters: (formal_parameters) @code_method.params
  body: (constructor_body) @code_method.body
) @code_method.def

; ============================================================================
; Field declarations with annotations
; ============================================================================

; Field with annotations (captures @Column, @Id, @JoinColumn, etc.)
(field_declaration
  (modifiers
    (marker_annotation
      name: (identifier) @code_field.annotation
    )?
    (annotation
      name: (identifier) @code_field.annotation
      arguments: (annotation_argument_list
        (element_value_pair
          key: (identifier) @code_field.annotation_key
          value: (_) @code_field.annotation_value
        )?
        (string_literal)? @code_field.annotation_default
      )?
    )?
  )?
  type: (_) @code_field.type
  declarator: (variable_declarator
    name: (identifier) @code_field.name
  )
) @code_field.def

; ============================================================================
; Import and package declarations
; ============================================================================

; Import declarations
(import_declaration
  (scoped_identifier) @import.module
) @import

; Package declaration
(package_declaration
  (scoped_identifier) @package.name
) @package

; ============================================================================
; Method invocations (for call graph)
; ============================================================================

; Method invocations - capture object for chained calls
(method_invocation
  object: (_)? @call.object
  name: (identifier) @call.method
  arguments: (argument_list) @call.args
) @call

; ============================================================================
; Comments
; ============================================================================

(line_comment) @comment
(block_comment) @comment
