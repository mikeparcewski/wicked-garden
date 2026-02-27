"""
Tree-based JSP Parser using lxml.

Extracts symbols with full nesting context and label resolution.
Uses tree parsing for accurate structural extraction instead of brittle regex.

Features:
- Control flow classification (c:if, c:forEach marked with is_control: true)
- Nesting context tracking (context_path, nesting_depth)
- Multi-strategy label resolution for data dictionary support
- Graceful fallback to regex if tree parsing fails
"""

import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

try:
    from lxml import etree
    LXML_AVAILABLE = True
except ImportError:
    LXML_AVAILABLE = False

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from symbol_graph import Symbol, SymbolType
from .base import register_parser


@register_parser('.jsp', '.jspx', '.jspf')
class JspParser:
    """Tree-based JSP parser with nesting context and label extraction."""

    CONTROL_TAGS = {'c:if', 'c:choose', 'c:when', 'c:otherwise', 'c:forEach', 'c:forTokens'}
    FORM_TAGS = {'form:input', 'form:select', 'form:textarea', 'form:checkbox',
                 'form:radiobutton', 'form:password', 'form:hidden', 'form:label'}

    # Form field indicators (for dynamic detection)
    FORM_TYPE_VALUES = {'text', 'hidden', 'password', 'checkbox', 'radio', 'select', 'textarea', 'file', 'date'}
    FORM_BINDING_ATTRS = {'path', 'name', 'ng-model', 'v-model', 'formcontrolname'}

    EL_PATTERN = re.compile(r'[$#]\{([^}]+)\}')

    def __init__(self):
        # Regex patterns for fallback parsing
        self.el_pattern = re.compile(r'([$#])\{([^}]+)\}')
        self.spring_form_pattern = re.compile(
            r'<form:(\w+)\s+([^>]*?)path\s*=\s*["\']([^"\']+)["\']',
            re.IGNORECASE | re.DOTALL
        )
        # Custom input tags with name= and type= attributes (e.g., apsp:validateInput)
        self.custom_input_pattern = re.compile(
            r'<(\w+:)?(\w*[Ii]nput\w*|\w*[Ff]ield\w*|\w*[Ss]elect\w*)\s+([^>]*?)'
            r'(?:name\s*=\s*["\']([^"\']+)["\'])',
            re.IGNORECASE | re.DOTALL
        )
        # Extract label attribute from custom tags
        self.label_attr_pattern = re.compile(
            r'label\s*=\s*["\']([^"\']+)["\']',
            re.IGNORECASE
        )
        # Extract type attribute
        self.type_attr_pattern = re.compile(
            r'type\s*=\s*["\']([^"\']+)["\']',
            re.IGNORECASE
        )

    def parse(self, content: str, file_path: str) -> List[Symbol]:
        """Parse JSP with tree-based extraction."""
        symbols = []

        # Add page symbol
        symbols.append(Symbol(
            id=f"jsp:{file_path}",
            type=SymbolType.JSP_PAGE,
            name=Path(file_path).name,
            qualified_name=file_path,
            file_path=file_path,
            line_start=1,
            metadata={"file_type": "jsp"},
        ))

        if LXML_AVAILABLE:
            try:
                normalized = self._preprocess_jsp(content)
                tree = self._parse_tree(normalized)

                # First pass: extract all labels
                labels = self._extract_labels(tree)

                # Second pass: extract symbols with label resolution
                self._walk_tree(tree, file_path, symbols, context_path=[], labels=labels)

            except Exception:
                # Fallback to regex if tree parsing fails
                symbols.extend(self._parse_with_regex(content, file_path))
        else:
            # No lxml available, use regex
            symbols.extend(self._parse_with_regex(content, file_path))

        return symbols

    def _extract_labels(self, tree) -> Dict[str, str]:
        """
        Extract all labels from the page.

        Returns dict mapping field identifiers to label text:
        - by 'for' attribute: labels["id:fieldId"] = "First Name"
        - by 'path' attribute: labels["path:person.name"] = "First Name"
        - by EL 'for': labels["el_for:data.fieldName"] = "First Name"
        """
        labels = {}

        for elem in tree.iter():
            tag = self._get_tag_name(elem)

            # HTML: <label for="fieldId">First Name</label>
            # Also handles: <label for="${data.fieldName}">
            if tag == 'label':
                for_attr = elem.get('for', '')
                text = self._get_element_text(elem)
                if for_attr and text:
                    # Clean the label text (remove colons, asterisks, extra whitespace)
                    clean_text = text.strip().rstrip(':').rstrip('*').strip()
                    # Collapse internal whitespace
                    clean_text = ' '.join(clean_text.split())
                    if clean_text:
                        # Check if for_attr is an EL expression
                        el_match = self.EL_PATTERN.search(for_attr)
                        if el_match:
                            # Store by EL expression content
                            el_expr = el_match.group(1)
                            labels[f"el_for:{el_expr}"] = clean_text
                        else:
                            labels[f"id:{for_attr}"] = clean_text

            # Spring: <form:label path="person.name">First Name</form:label>
            elif tag == 'form:label':
                path = elem.get('path', '')
                text = self._get_element_text(elem)
                if path and text:
                    labels[f"path:{path}"] = text.strip()

            # fmt:message with key (i18n) - store key as placeholder
            elif tag == 'fmt:message':
                key = elem.get('key', '')
                var = elem.get('var', '')
                if key:
                    labels[f"i18n:{key}"] = f"[{key}]"
                    if var:
                        labels[f"var:{var}"] = f"[{key}]"

        # Second pass: resolve EL variable references in label text
        resolved_labels = {}
        for label_key, label_text in labels.items():
            resolved_text = label_text
            # Find all ${varName} in label text and substitute
            for var_match in self.EL_PATTERN.finditer(label_text):
                var_name = var_match.group(1).strip()
                if f"var:{var_name}" in labels:
                    resolved_text = resolved_text.replace(
                        var_match.group(0),
                        labels[f"var:{var_name}"]
                    )
            # Clean up after substitution
            resolved_text = resolved_text.strip().rstrip(':').rstrip('*').strip()
            resolved_text = ' '.join(resolved_text.split())
            resolved_labels[label_key] = resolved_text

        return resolved_labels

    def _get_element_text(self, element) -> str:
        """Get all text content from element, including children."""
        return ''.join(element.itertext()).strip()

    def _resolve_label(self, element, path: str, labels: Dict[str, str]) -> Tuple[Optional[str], Optional[str]]:
        """
        Resolve label for a form field using multiple strategies.

        Returns: (label_text, source) tuple

        Resolution order (first match wins):
        1. By id attribute -> labels["id:{id}"]
        2. By path attribute -> labels["path:{path}"]
        3. Direct label attribute on custom tags
        4. Placeholder attribute (common in modern forms)
        5. Title attribute (accessibility fallback)
        6. ARIA label (accessibility)
        7. Previous sibling text (table layouts)
        8. Parent cell's previous sibling (nested tables)
        """
        # 1. Try by id
        field_id = element.get('id', '')
        if field_id and f"id:{field_id}" in labels:
            return labels[f"id:{field_id}"], "label_for_id"

        # 2. Try by path
        if path and f"path:{path}" in labels:
            return labels[f"path:{path}"], "form_label_path"

        # 2b. Try by EL for attribute (dynamic name binding)
        if path and f"el_for:{path}" in labels:
            return labels[f"el_for:{path}"], "label_for_el"

        # 3. Try direct label attribute (custom tags like apsp:validateInput)
        direct_label = element.get('label', '')
        if direct_label:
            # Check if it's an EL expression referencing a variable
            el_match = self.EL_PATTERN.search(direct_label)
            if el_match:
                var_ref = el_match.group(1)
                if f"var:{var_ref}" in labels:
                    return labels[f"var:{var_ref}"], "label_attr_i18n"
            else:
                return direct_label, "label_attr"

        # 4. Try placeholder attribute
        placeholder = element.get('placeholder', '')
        if placeholder:
            return placeholder, "placeholder"

        # 5. Try title attribute
        title = element.get('title', '')
        if title:
            return title, "title"

        # 6. Try ARIA label
        aria_label = element.get('aria-label', '')
        if aria_label:
            return aria_label, "aria_label"

        # 7. Previous sibling text (common in table layouts)
        prev = element.getprevious()
        if prev is not None:
            prev_tag = self._get_tag_name(prev)
            if prev_tag in ('td', 'th', 'span', 'div', 'label'):
                text = self._get_element_text(prev).strip(':').strip()
                if text and len(text) < 50:  # Reasonable label length
                    return text, "sibling_text"

        # 8. Parent cell's previous sibling (nested table structures)
        parent = element.getparent()
        if parent is not None:
            parent_tag = self._get_tag_name(parent)
            if parent_tag == 'td':
                prev_td = parent.getprevious()
                if prev_td is not None:
                    prev_td_tag = self._get_tag_name(prev_td)
                    if prev_td_tag in ('td', 'th'):
                        text = self._get_element_text(prev_td).strip(':').strip()
                        if text and len(text) < 50:
                            return text, "table_cell_sibling"

                # 8b. Try table header (th) in same column position
                th_label = self._find_table_header(parent)
                if th_label:
                    return th_label, "table_header"

        # 9. Infer from field name (last resort for data dictionary)
        if path:
            inferred = self._infer_label_from_name(path)
            if inferred:
                return inferred, "inferred_from_name"

        return None, None

    def _find_table_header(self, td_element) -> Optional[str]:
        """Find the table header (th) for this cell's column."""
        try:
            # Count column position
            col_index = 0
            sibling = td_element.getprevious()
            while sibling is not None:
                if self._get_tag_name(sibling) in ('td', 'th'):
                    col_index += 1
                sibling = sibling.getprevious()

            # Walk up to find table, then find header row
            parent = td_element.getparent()
            while parent is not None:
                if self._get_tag_name(parent) == 'table':
                    # Find thead or first tr with th elements
                    for row in parent.iter():
                        if self._get_tag_name(row) == 'tr':
                            headers = [c for c in row if self._get_tag_name(c) == 'th']
                            if headers and col_index < len(headers):
                                text = self._get_element_text(headers[col_index]).strip(':').strip()
                                if text and len(text) < 50:
                                    return text
                            break  # Only check first row
                    break
                parent = parent.getparent()
        except Exception:
            pass
        return None

    def _infer_label_from_name(self, name: str) -> Optional[str]:
        """
        Infer a human-readable label from field name.

        Handles:
        - camelCase: personFirstName -> Person First Name
        - SCREAMING_SNAKE: PERSON_FIRST_NAME -> Person First Name
        - dot.paths: person.firstName -> First Name (last segment)
        - EL expressions: data.citizenshipAttributeNames.FIELD -> Field

        Filters out:
        - Hidden field indicators
        - Technical suffixes (_EXT, _ID, etc.)
        """
        if not name:
            return None

        # Extract the meaningful part (last path segment, or after last dot in EL)
        if '.' in name:
            segments = name.split('.')
            # Skip common prefixes like 'data', 'form', 'model'
            meaningful = [s for s in segments if s.lower() not in
                         ('data', 'form', 'model', 'command', 'attributenames',
                          'citizenshipattributenames', 'personattributenames')]
            name = meaningful[-1] if meaningful else segments[-1]

        # Skip if it looks like a hidden/technical field
        skip_patterns = ('HIDDEN', 'COUNTERPART', '_EXT', 'REQUEST_PARAMETER',
                        'ACTION', 'MODE', 'STYLE', 'REQUIRED')
        if any(p in name.upper() for p in skip_patterns):
            return None

        # Convert to readable form
        import re

        # Handle SCREAMING_SNAKE_CASE
        if '_' in name and name.isupper():
            words = name.split('_')
            words = [w.capitalize() for w in words if w]
            return ' '.join(words)

        # Handle camelCase or PascalCase
        # Insert space before uppercase letters
        spaced = re.sub(r'([a-z])([A-Z])', r'\1 \2', name)
        # Handle consecutive caps (like 'INS' in 'INSDocument')
        spaced = re.sub(r'([A-Z]+)([A-Z][a-z])', r'\1 \2', spaced)
        # Clean up underscores
        spaced = spaced.replace('_', ' ')
        # Title case
        words = spaced.split()
        result = ' '.join(w.capitalize() for w in words if w)

        return result if result and len(result) > 1 else None

    def _preprocess_jsp(self, content: str) -> str:
        """Normalize JSP for XML parsing."""
        # Remove JSP scriptlets and directives (except taglibs we want to track)
        content = re.sub(r'<%@\s*page[^%]*%>', '', content)
        content = re.sub(r'<%[^@%][^%]*%>', '', content)
        content = re.sub(r'<%=[^%]*%>', '', content)
        # Wrap in root element
        return f'<root>{content}</root>'

    def _parse_tree(self, content: str):
        """Parse content as XML/HTML tree."""
        try:
            return etree.fromstring(content.encode())
        except Exception:
            parser = etree.HTMLParser(recover=True)
            return etree.fromstring(content.encode(), parser)

    def _walk_tree(self, element, file_path: str, symbols: List[Symbol],
                   context_path: List[str], labels: Dict[str, str]):
        """Recursively walk tree, extracting symbols with context."""
        tag = self._get_tag_name(element)

        new_context = context_path.copy()
        if tag in self.CONTROL_TAGS or tag in self.FORM_TAGS:
            new_context.append(tag)

        self._extract_from_element(element, file_path, symbols, new_context, labels)

        for child in element:
            self._walk_tree(child, file_path, symbols, new_context, labels)

    def _get_tag_name(self, element) -> str:
        """Get tag name, handling namespaces."""
        tag = element.tag
        if isinstance(tag, str):
            if '}' in tag:
                tag = tag.split('}')[1]
            return tag.lower()
        return ''

    def _is_form_field(self, element) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Dynamically detect if element is a form field based on attributes.

        Returns: (is_form_field, binding_value, binding_type)

        Detection heuristics:
        1. Has 'path' attribute (Spring form binding)
        2. Has 'name' attribute + input-like 'type' attribute
        3. Has 'name' attribute + tag suggests input (validateinput, input, select, etc.)
        4. Has ng-model, v-model, formControlName (Angular/Vue)
        """
        attribs = {k.lower(): v for k, v in element.attrib.items()}
        tag = self._get_tag_name(element)

        # 1. Spring form:* path binding
        if 'path' in attribs:
            return True, attribs['path'], 'path'

        # 2. Has name + type indicates form input
        if 'name' in attribs:
            type_val = attribs.get('type', '').lower()
            if type_val in self.FORM_TYPE_VALUES:
                return True, attribs['name'], 'name'

            # 3. Tag name suggests input (contains 'input', 'select', 'textarea', etc.)
            input_keywords = ('input', 'select', 'textarea', 'checkbox', 'radio', 'field')
            if any(kw in tag for kw in input_keywords):
                return True, attribs['name'], 'name'

        # 4. Angular/Vue model bindings
        for attr in ('ng-model', 'v-model', 'formcontrolname', '[(ngmodel)]'):
            if attr in attribs:
                return True, attribs[attr], attr

        return False, None, None

    def _extract_from_element(self, element, file_path: str,
                               symbols: List[Symbol], context_path: List[str],
                               labels: Dict[str, str]):
        """Extract symbols from element and its attributes."""
        tag = self._get_tag_name(element)
        line = getattr(element, 'sourceline', None) or 1

        # Extract control flow symbols
        if tag in self.CONTROL_TAGS:
            test_expr = element.get('test', '')
            items_expr = element.get('items', '')
            var_name = element.get('var', '')

            symbols.append(Symbol(
                id=f"jstl:{file_path}:{line}:{tag}",
                type=SymbolType.JSTL_VARIABLE,
                name=var_name or test_expr or items_expr or tag,
                qualified_name=f"{file_path}#{tag}:{line}",
                file_path=file_path,
                line_start=line,
                label=None,  # Control flow doesn't have labels
                metadata={
                    "is_control": True,
                    "control_type": tag,
                    "test": test_expr,
                    "items": items_expr,
                    "var": var_name,
                    "context_path": ' > '.join(context_path) if context_path else 'root',
                    "nesting_depth": len(context_path),
                },
            ))

        # Extract form field symbols with label resolution (dynamic detection)
        is_form, binding_value, binding_type = self._is_form_field(element)
        if is_form and binding_value:
            # Resolve EL expressions in binding value
            el_match = self.EL_PATTERN.search(binding_value)
            binding_expr = el_match.group(1) if el_match else binding_value
            segments = self._decompose_el_path(binding_expr) if el_match else binding_value.split('.')

            # Detect hidden fields
            type_attr = element.get('type', '').lower()
            is_hidden = (
                type_attr == 'hidden' or
                'HIDDEN' in binding_expr.upper() or
                'COUNTERPART' in binding_expr.upper()
            )

            resolved_label, label_source = self._resolve_label(element, binding_expr, labels)

            symbols.append(Symbol(
                id=f"form:{file_path}:{line}:{binding_expr[:50]}",
                type=SymbolType.FORM_BINDING,
                name=binding_expr,
                qualified_name=f"{file_path}#form:{binding_expr}",
                file_path=file_path,
                line_start=line,
                label=resolved_label,
                metadata={
                    "is_control": False,
                    "is_hidden": is_hidden,
                    "tag_type": tag,
                    "binding_type": binding_type,  # 'path', 'name', 'ng-model', etc.
                    "path_segments": segments,
                    "root_bean": segments[0] if segments else None,
                    "context_path": ' > '.join(context_path) if context_path else 'root',
                    "nesting_depth": len(context_path),
                    "in_control_flow": any(t in self.CONTROL_TAGS for t in context_path),
                    "label_source": label_source,
                },
            ))

        # Extract EL expressions from attributes
        for attr_name, attr_value in element.attrib.items():
            for match in self.EL_PATTERN.finditer(str(attr_value)):
                expr = match.group(1)
                segments = self._decompose_el_path(expr)

                symbols.append(Symbol(
                    id=f"el:{file_path}:{line}:{expr[:30]}",
                    type=SymbolType.EL_EXPRESSION,
                    name=expr,
                    qualified_name=f"{file_path}#{expr}",
                    file_path=file_path,
                    line_start=line,
                    label=None,  # EL expressions don't have labels
                    metadata={
                        "is_control": tag in self.CONTROL_TAGS,
                        "in_attribute": attr_name,
                        "path_segments": segments,
                        "root_bean": segments[0] if segments else None,
                        "context_path": ' > '.join(context_path) if context_path else 'root',
                        "nesting_depth": len(context_path),
                        "in_control_flow": any(t in self.CONTROL_TAGS for t in context_path),
                    },
                ))

        # Extract EL from text content
        if element.text:
            for match in self.EL_PATTERN.finditer(element.text):
                expr = match.group(1)
                segments = self._decompose_el_path(expr)

                symbols.append(Symbol(
                    id=f"el:{file_path}:{line}:text:{expr[:30]}",
                    type=SymbolType.EL_EXPRESSION,
                    name=expr,
                    qualified_name=f"{file_path}#text:{expr}",
                    file_path=file_path,
                    line_start=line,
                    label=None,
                    metadata={
                        "is_control": False,
                        "in_text": True,
                        "path_segments": segments,
                        "root_bean": segments[0] if segments else None,
                        "context_path": ' > '.join(context_path) if context_path else 'root',
                        "nesting_depth": len(context_path),
                        "in_control_flow": any(t in self.CONTROL_TAGS for t in context_path),
                    },
                ))

    def _decompose_el_path(self, expr: str) -> List[str]:
        """Decompose EL expression into path segments."""
        # Remove method calls
        clean = re.sub(r'\([^)]*\)', '', expr)
        # Remove operators and everything after
        clean = re.sub(r'\s*[?:&|!=<>]+.*', '', clean)
        clean = clean.strip()

        if not clean:
            return []

        # Split on dots and brackets
        segments = re.split(r'[.\[\]]+', clean)
        return [s.strip("'\"") for s in segments if s.strip("'\"")]

    def _parse_with_regex(self, content: str, file_path: str) -> List[Symbol]:
        """Fallback regex parsing if tree fails."""
        symbols = []

        # Parse EL expressions
        for match in self.el_pattern.finditer(content):
            el_type = match.group(1)
            expr = match.group(2).strip()
            line = content[:match.start()].count('\n') + 1

            if expr:
                segments = self._decompose_el_path(expr)
                if segments:
                    symbols.append(Symbol(
                        id=f"el:{file_path}:{line}:{expr[:30]}",
                        type=SymbolType.EL_EXPRESSION,
                        name=expr,
                        qualified_name=f"{file_path}#{expr}",
                        file_path=file_path,
                        line_start=line,
                        metadata={
                            "raw": f"{el_type}{{{expr}}}",
                            "path_segments": segments,
                            "root_bean": segments[0] if segments else "",
                            "parser_mode": "regex_fallback",
                        },
                    ))

        # Parse Spring form tags
        for match in self.spring_form_pattern.finditer(content):
            tag_name = match.group(1)
            path = match.group(3)
            line = content[:match.start()].count('\n') + 1

            segments = path.split('.')
            symbols.append(Symbol(
                id=f"form:{file_path}:{line}:{path}",
                type=SymbolType.FORM_BINDING,
                name=path,
                qualified_name=f"{file_path}#form:{path}",
                file_path=file_path,
                line_start=line,
                metadata={
                    "tag": f"form:{tag_name}",
                    "path_segments": segments,
                    "root_bean": segments[0] if segments else "",
                    "parser_mode": "regex_fallback",
                },
            ))

        # Parse custom input tags (e.g., apsp:validateInput, custom:inputField)
        seen_names = set()  # Avoid duplicates
        for match in self.custom_input_pattern.finditer(content):
            prefix = match.group(1) or ''
            tag_name = match.group(2)
            attrs_text = match.group(3)
            name = match.group(4)

            if not name or name in seen_names:
                continue
            seen_names.add(name)

            line = content[:match.start()].count('\n') + 1

            # Extract label and type from attributes
            label_match = self.label_attr_pattern.search(attrs_text)
            type_match = self.type_attr_pattern.search(attrs_text)

            label = label_match.group(1) if label_match else None
            field_type = type_match.group(1).lower() if type_match else 'text'

            # Detect hidden fields
            is_hidden = (
                field_type == 'hidden' or
                'HIDDEN' in name.upper() or
                'COUNTERPART' in name.upper()
            )

            segments = name.split('.')
            symbols.append(Symbol(
                id=f"form:{file_path}:{line}:{name}",
                type=SymbolType.FORM_BINDING,
                name=name,
                qualified_name=f"{file_path}#form:{name}",
                file_path=file_path,
                line_start=line,
                label=label,
                metadata={
                    "tag": f"{prefix}{tag_name}",
                    "path_segments": segments,
                    "root_bean": segments[0] if segments else "",
                    "field_type": field_type,
                    "is_hidden": is_hidden,
                    "label_source": "label_attr" if label else None,
                    "parser_mode": "regex_fallback",
                },
            ))

        return symbols
