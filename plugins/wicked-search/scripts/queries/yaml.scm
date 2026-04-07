; YAML query patterns for configuration files

; Top-level mapping pairs (key-value at root level)
(document
  (block_node
    (block_mapping
      (block_mapping_pair
        key: (flow_node) @code_variable.name
        value: (_)) @code_variable.def)))

; All block mapping pairs (nested configurations)
(block_mapping_pair
  key: (flow_node) @code_variable.name) @code_variable.def
