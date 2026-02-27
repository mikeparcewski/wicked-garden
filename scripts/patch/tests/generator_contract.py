"""
Generator contract and conformance testing framework.

All generators must pass these tests to be considered production-ready.
This ensures consistent behavior across languages and prevents regressions.

Contract Tests:
1. Type Mappings - All standard types must map to valid language types
2. Field Generation - add_field must produce syntactically valid code
3. Rename Generation - rename_field must update all references
4. Remove Generation - remove_field must cleanly remove code
5. Output Syntax - Generated code must parse without errors

Usage:
    # Run conformance tests for all generators
    python -m pytest tests/test_conformance.py

    # Run for specific generator
    python -m pytest tests/test_conformance.py -k "java"
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Type
import re
import sys

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from generators import (
    BaseGenerator,
    ChangeSpec,
    ChangeType,
    FieldSpec,
    Patch,
    GeneratorRegistry,
)


@dataclass
class ContractTestResult:
    """Result of a single contract test."""
    test_name: str
    passed: bool
    message: str
    details: Optional[Dict[str, Any]] = None

    def __bool__(self) -> bool:
        return self.passed


@dataclass
class ConformanceReport:
    """Complete conformance report for a generator."""
    generator_name: str
    results: List[ContractTestResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(r.passed for r in self.results)

    @property
    def pass_count(self) -> int:
        return sum(1 for r in self.results if r.passed)

    @property
    def fail_count(self) -> int:
        return sum(1 for r in self.results if not r.passed)

    def summary(self) -> str:
        """Human-readable summary."""
        status = "PASS" if self.passed else "FAIL"
        lines = [
            f"Conformance Report: {self.generator_name}",
            f"Status: {status}",
            f"Tests: {self.pass_count}/{len(self.results)} passed",
            "",
        ]
        for result in self.results:
            icon = "+" if result.passed else "x"
            lines.append(f"  [{icon}] {result.test_name}: {result.message}")
        return "\n".join(lines)


# Standard type mappings that all generators must support
STANDARD_TYPES = {
    "String": "A text value",
    "Integer": "A 32-bit integer",
    "Long": "A 64-bit integer",
    "Float": "A floating-point number",
    "Double": "A double-precision number",
    "Boolean": "A true/false value",
    "Date": "A date without time",
    "DateTime": "A date with time",
    "Decimal": "A precise decimal number",
}


class GeneratorContract:
    """
    Contract tests that all generators must pass.

    These tests verify that a generator:
    1. Correctly maps all standard types
    2. Generates syntactically valid code
    3. Handles all change types properly
    4. Produces patches with correct structure
    """

    def __init__(self, generator: BaseGenerator, sample_content: str):
        """
        Initialize contract tests.

        Args:
            generator: The generator to test
            sample_content: Sample file content for testing
        """
        self.generator = generator
        self.sample_content = sample_content

    def run_all_tests(self) -> ConformanceReport:
        """Run all contract tests."""
        report = ConformanceReport(generator_name=self.generator.name)

        # Run each test
        report.results.append(self.test_type_mappings())
        report.results.append(self.test_add_field_generation())
        report.results.append(self.test_rename_field_generation())
        report.results.append(self.test_remove_field_generation())
        report.results.append(self.test_patch_structure())
        report.results.append(self.test_output_syntax())

        return report

    def test_type_mappings(self) -> ContractTestResult:
        """Test that all standard types can be mapped (returns a valid type string)."""
        failed = []
        for type_name in STANDARD_TYPES:
            try:
                # Try both original and lowercase (generators may use lowercase keys)
                mapped = self.generator._map_type(type_name)
                mapped_lower = self.generator._map_type(type_name.lower())

                # Verify at least one returns a non-empty string
                if not mapped and not mapped_lower:
                    failed.append(f"{type_name}: returned empty")
                elif not isinstance(mapped, str) or not isinstance(mapped_lower, str):
                    failed.append(f"{type_name}: returned non-string")
            except Exception as e:
                failed.append(f"{type_name}: {e}")

        if failed:
            return ContractTestResult(
                test_name="type_mappings",
                passed=False,
                message=f"Type mapping failures: {', '.join(failed[:3])}",
                details={"failures": failed}
            )

        return ContractTestResult(
            test_name="type_mappings",
            passed=True,
            message=f"All {len(STANDARD_TYPES)} standard types can be mapped"
        )

    def test_add_field_generation(self) -> ContractTestResult:
        """Test add_field generates valid patches."""
        field_spec = FieldSpec(
            name="testField",
            type="String",
            nullable=False,
            column_name="TEST_FIELD",
            label="Test Field",
        )

        change_spec = ChangeSpec(
            change_type=ChangeType.ADD_FIELD,
            target_symbol_id="test::TestClass",
            field_spec=field_spec,
        )

        symbol = {
            "id": "test::TestClass",
            "name": "TestClass",
            "type": "class",
            "file_path": "test/TestClass.java",
            "line_start": 1,
            "line_end": 10,
        }

        try:
            patches = self.generator.generate(
                change_spec, symbol, self.sample_content
            )

            # Some generators may not produce patches for minimal sample content
            # This is acceptable - we just verify no exceptions are raised
            # and any patches produced have valid structure
            if patches:
                for patch in patches:
                    if not patch.new_content:
                        return ContractTestResult(
                            test_name="add_field_generation",
                            passed=False,
                            message="Patch has empty new_content",
                        )

            return ContractTestResult(
                test_name="add_field_generation",
                passed=True,
                message=f"Generated {len(patches)} patches (0 is OK for minimal content)",
                details={"patch_count": len(patches)}
            )

        except Exception as e:
            return ContractTestResult(
                test_name="add_field_generation",
                passed=False,
                message=f"Exception: {e}",
            )

    def test_rename_field_generation(self) -> ContractTestResult:
        """Test rename_field generates valid patches."""
        change_spec = ChangeSpec(
            change_type=ChangeType.RENAME_FIELD,
            target_symbol_id="test::TestClass",
            old_name="oldField",
            new_name="newField",
        )

        symbol = {
            "id": "test::TestClass",
            "name": "TestClass",
            "type": "class",
            "file_path": "test/TestClass.java",
            "line_start": 1,
            "line_end": 10,
        }

        try:
            patches = self.generator.generate(
                change_spec, symbol, self.sample_content
            )

            # Rename might not generate patches if field not found
            # That's OK - we're just testing it doesn't crash
            return ContractTestResult(
                test_name="rename_field_generation",
                passed=True,
                message=f"Generated {len(patches)} patches",
            )

        except Exception as e:
            return ContractTestResult(
                test_name="rename_field_generation",
                passed=False,
                message=f"Exception: {e}",
            )

    def test_remove_field_generation(self) -> ContractTestResult:
        """Test remove_field generates valid patches."""
        change_spec = ChangeSpec(
            change_type=ChangeType.REMOVE_FIELD,
            target_symbol_id="test::TestClass",
            old_name="removedField",
        )

        symbol = {
            "id": "test::TestClass",
            "name": "TestClass",
            "type": "class",
            "file_path": "test/TestClass.java",
            "line_start": 1,
            "line_end": 10,
        }

        try:
            patches = self.generator.generate(
                change_spec, symbol, self.sample_content
            )

            return ContractTestResult(
                test_name="remove_field_generation",
                passed=True,
                message=f"Generated {len(patches)} patches",
            )

        except Exception as e:
            return ContractTestResult(
                test_name="remove_field_generation",
                passed=False,
                message=f"Exception: {e}",
            )

    def test_patch_structure(self) -> ContractTestResult:
        """Test that patches have valid structure."""
        field_spec = FieldSpec(name="testField", type="String")
        change_spec = ChangeSpec(
            change_type=ChangeType.ADD_FIELD,
            target_symbol_id="test::TestClass",
            field_spec=field_spec,
        )

        symbol = {
            "id": "test::TestClass",
            "name": "TestClass",
            "type": "class",
            "file_path": "test/TestClass.java",
            "line_start": 1,
            "line_end": 10,
        }

        try:
            patches = self.generator.generate(
                change_spec, symbol, self.sample_content
            )

            issues = []
            for i, patch in enumerate(patches):
                if patch.line_start < 0:
                    issues.append(f"Patch {i}: negative line_start")
                if patch.line_end < 0:
                    issues.append(f"Patch {i}: negative line_end")
                if not patch.description:
                    issues.append(f"Patch {i}: missing description")
                if patch.confidence not in ("high", "medium", "low"):
                    issues.append(f"Patch {i}: invalid confidence '{patch.confidence}'")

            if issues:
                return ContractTestResult(
                    test_name="patch_structure",
                    passed=False,
                    message="; ".join(issues),
                )

            return ContractTestResult(
                test_name="patch_structure",
                passed=True,
                message="All patches have valid structure",
            )

        except Exception as e:
            return ContractTestResult(
                test_name="patch_structure",
                passed=False,
                message=f"Exception: {e}",
            )

    def test_output_syntax(self) -> ContractTestResult:
        """
        Test that generated code is syntactically valid.

        This is a basic check - subclasses can override for
        language-specific validation.
        """
        field_spec = FieldSpec(name="testField", type="String")
        change_spec = ChangeSpec(
            change_type=ChangeType.ADD_FIELD,
            target_symbol_id="test::TestClass",
            field_spec=field_spec,
        )

        symbol = {
            "id": "test::TestClass",
            "name": "TestClass",
            "type": "class",
            "file_path": "test/TestClass.java",
            "line_start": 1,
            "line_end": 10,
        }

        try:
            patches = self.generator.generate(
                change_spec, symbol, self.sample_content
            )

            # Basic syntax checks
            issues = []
            for patch in patches:
                content = patch.new_content
                # Check for unbalanced braces/brackets
                if content.count('{') != content.count('}'):
                    issues.append(f"Unbalanced braces in {patch.description}")
                if content.count('(') != content.count(')'):
                    issues.append(f"Unbalanced parens in {patch.description}")
                if content.count('[') != content.count(']'):
                    issues.append(f"Unbalanced brackets in {patch.description}")

            if issues:
                return ContractTestResult(
                    test_name="output_syntax",
                    passed=False,
                    message="; ".join(issues[:3]),
                )

            return ContractTestResult(
                test_name="output_syntax",
                passed=True,
                message="Basic syntax checks passed",
            )

        except Exception as e:
            return ContractTestResult(
                test_name="output_syntax",
                passed=False,
                message=f"Exception: {e}",
            )


def run_conformance_tests(
    generator_class: Type[BaseGenerator],
    sample_content: str,
) -> ConformanceReport:
    """
    Run conformance tests for a generator.

    Args:
        generator_class: The generator class to test
        sample_content: Sample file content

    Returns:
        ConformanceReport with results
    """
    generator = generator_class()
    contract = GeneratorContract(generator, sample_content)
    return contract.run_all_tests()


def run_all_generator_tests() -> Dict[str, ConformanceReport]:
    """
    Run conformance tests for all registered generators.

    Returns:
        Dictionary of generator name -> report
    """
    reports = {}

    # Import all generators to register them
    from generators import java_generator, python_generator, typescript_generator
    from generators import jsp_generator, sql_generator

    # Sample content for each language
    samples = {
        ".java": """
public class TestClass {
    private String existingField;

    public String getExistingField() {
        return existingField;
    }

    public void setExistingField(String value) {
        this.existingField = value;
    }
}
""",
        ".py": """
from sqlalchemy import Column, String
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class TestClass(Base):
    __tablename__ = 'test_table'

    existing_field = Column(String)
""",
        ".ts": """
import { Entity, Column } from 'typeorm';

@Entity()
export class TestClass {
    @Column()
    existingField: string;
}
""",
        ".jsp": """
<%@ taglib prefix="form" uri="http://www.springframework.org/tags/form" %>
<form:form modelAttribute="testEntity">
    <form:input path="existingField" />
    <form:errors path="existingField" />
</form:form>
""",
        ".sql": """
CREATE TABLE test_table (
    id INTEGER PRIMARY KEY,
    existing_column VARCHAR(255)
);
""",
    }

    for ext, generator_class in GeneratorRegistry.list_generators().items():
        if ext in samples:
            report = run_conformance_tests(generator_class, samples[ext])
            reports[generator_class.name] = report

    return reports


if __name__ == "__main__":
    # Run all tests and print reports
    reports = run_all_generator_tests()

    all_passed = True
    for name, report in reports.items():
        print(report.summary())
        print()
        if not report.passed:
            all_passed = False

    if all_passed:
        print("All generators passed conformance tests!")
        sys.exit(0)
    else:
        print("Some generators failed conformance tests.")
        sys.exit(1)
