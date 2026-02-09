; R tree-sitter queries for extracting code symbols and relationships
; Converted from r-tags.scm

(binary_operator
    lhs: (identifier) @code_function.name
    operator: "<-"
    rhs: (function_definition)
) @code_function.def

(binary_operator
    lhs: (identifier) @code_function.name
    operator: "="
    rhs: (function_definition)
) @code_function.def

(call
    function: (identifier) @call.function
) @call.ref

(call
    function: (namespace_operator
        rhs: (identifier) @call.function
    )
) @call.ref
