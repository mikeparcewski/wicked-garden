"""
Conformance tests for wicked-patch generators.

Runs contract tests and golden tests for all registered generators.

Usage:
    # Run all tests
    python test_conformance.py

    # Run with pytest
    pytest test_conformance.py -v

    # Run specific generator
    pytest test_conformance.py -k "java"
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Any

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
from tests.generator_contract import (
    GeneratorContract,
    ConformanceReport,
    run_conformance_tests,
)


FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_fixtures() -> Dict[str, Dict[str, Any]]:
    """Load all golden test fixtures."""
    fixtures = {}
    for fixture_file in FIXTURES_DIR.glob("*.json"):
        with open(fixture_file) as f:
            data = json.load(f)
            fixtures[data["name"]] = data
    return fixtures


class TestGeneratorContract:
    """Contract tests for generators."""

    def test_java_generator_contract(self):
        """Java generator passes all contract tests."""
        from generators.java_generator import JavaGenerator

        sample = """
public class TestClass {
    private String existingField;
}
"""
        report = run_conformance_tests(JavaGenerator, sample)
        assert report.passed, report.summary()

    def test_python_generator_contract(self):
        """Python generator passes all contract tests."""
        from generators.python_generator import PythonGenerator

        sample = """
from sqlalchemy import Column, String

class TestClass:
    existing_field = Column(String)
"""
        report = run_conformance_tests(PythonGenerator, sample)
        assert report.passed, report.summary()

    def test_typescript_generator_contract(self):
        """TypeScript generator passes all contract tests."""
        from generators.typescript_generator import TypeScriptGenerator

        sample = """
export class TestClass {
    existingField: string;
}
"""
        report = run_conformance_tests(TypeScriptGenerator, sample)
        assert report.passed, report.summary()

    def test_jsp_generator_contract(self):
        """JSP generator passes all contract tests."""
        from generators.jsp_generator import JSPGenerator

        sample = """
<form:form modelAttribute="entity">
    <form:input path="existingField" />
</form:form>
"""
        report = run_conformance_tests(JSPGenerator, sample)
        assert report.passed, report.summary()

    def test_sql_generator_contract(self):
        """SQL generator passes all contract tests."""
        from generators.sql_generator import SQLGenerator

        sample = """
CREATE TABLE test_table (
    id INTEGER PRIMARY KEY
);
"""
        report = run_conformance_tests(SQLGenerator, sample)
        assert report.passed, report.summary()

    def test_go_generator_contract(self):
        """Go generator passes all contract tests."""
        from generators.go_generator import GoGenerator

        sample = """
type TestClass struct {
    ExistingField string `json:"existing_field"`
}
"""
        report = run_conformance_tests(GoGenerator, sample)
        assert report.passed, report.summary()

    def test_csharp_generator_contract(self):
        """C# generator passes all contract tests."""
        from generators.csharp_generator import CSharpGenerator

        sample = """
public class TestClass
{
    public string ExistingField { get; set; }
}
"""
        report = run_conformance_tests(CSharpGenerator, sample)
        assert report.passed, report.summary()

    def test_ruby_generator_contract(self):
        """Ruby generator passes all contract tests."""
        from generators.ruby_generator import RubyGenerator

        sample = """
class TestClass < ApplicationRecord
  attr_accessor :existing_field
end
"""
        report = run_conformance_tests(RubyGenerator, sample)
        assert report.passed, report.summary()

    def test_kotlin_generator_contract(self):
        """Kotlin generator passes all contract tests."""
        from generators.kotlin_generator import KotlinGenerator

        sample = """
data class TestClass(
    val existingField: String
)
"""
        report = run_conformance_tests(KotlinGenerator, sample)
        assert report.passed, report.summary()

    def test_rust_generator_contract(self):
        """Rust generator passes all contract tests."""
        from generators.rust_generator import RustGenerator

        sample = """
pub struct TestClass {
    pub existing_field: String,
}
"""
        report = run_conformance_tests(RustGenerator, sample)
        assert report.passed, report.summary()

    def test_php_generator_contract(self):
        """PHP generator passes all contract tests."""
        from generators.php_generator import PHPGenerator

        sample = """
class TestClass
{
    private string $existingField;
}
"""
        report = run_conformance_tests(PHPGenerator, sample)
        assert report.passed, report.summary()

    def test_perl_generator_contract(self):
        """Perl generator passes all contract tests."""
        from generators.perl_generator import PerlGenerator

        sample = """
package TestClass;
use Moose;

has 'existing_field' => (
    is  => 'rw',
    isa => 'Str',
);

1;
"""
        report = run_conformance_tests(PerlGenerator, sample)
        assert report.passed, report.summary()


class TestGoldenOutput:
    """Golden output tests for generators."""

    def _run_golden_test(self, fixture_name: str):
        """Run a golden test from a fixture file."""
        fixtures = load_fixtures()
        if fixture_name not in fixtures:
            raise ValueError(f"Fixture not found: {fixture_name}")

        fixture = fixtures[fixture_name]
        input_data = fixture["input"]
        expected = fixture["expected"]

        # Get generator
        generator_name = fixture["generator"]
        ext_map = {
            "java": ".java",
            "python": ".py",
            "typescript": ".ts",
            "jsp": ".jsp",
            "sql": ".sql",
            "go": ".go",
            "csharp": ".cs",
            "ruby": ".rb",
            "kotlin": ".kt",
            "rust": ".rs",
            "php": ".php",
            "perl": ".pm",
        }
        ext = ext_map.get(generator_name)
        generator_class = GeneratorRegistry.list_generators().get(ext)
        assert generator_class is not None, f"Generator not found for {generator_name}"

        generator = generator_class()

        # Build change spec
        field_spec = None
        if "field_spec" in input_data:
            fs = input_data["field_spec"]
            field_spec = FieldSpec(
                name=fs["name"],
                type=fs["type"],
                nullable=fs.get("nullable", True),
                column_name=fs.get("column_name"),
                label=fs.get("label"),
            )

        change_spec = ChangeSpec(
            change_type=ChangeType(input_data["change_type"]),
            target_symbol_id=input_data["symbol"]["id"],
            field_spec=field_spec,
            old_name=input_data.get("old_name"),
            new_name=input_data.get("new_name"),
        )

        # Generate patches
        patches = generator.generate(
            change_spec,
            input_data["symbol"],
            input_data["sample_content"],
        )

        # Validate expectations
        if "patch_count_min" in expected:
            assert len(patches) >= expected["patch_count_min"], \
                f"Expected at least {expected['patch_count_min']} patches, got {len(patches)}"

        # Check must_contain
        all_content = "\n".join(p.new_content for p in patches)
        for required in expected.get("must_contain", []):
            assert required in all_content, \
                f"Expected '{required}' in output, got:\n{all_content}"

        # Check must_not_contain
        for forbidden in expected.get("must_not_contain", []):
            assert forbidden not in all_content, \
                f"Forbidden '{forbidden}' found in output:\n{all_content}"

    def test_java_add_field(self):
        """Java add_field golden test."""
        self._run_golden_test("java_add_field")

    def test_python_add_field(self):
        """Python add_field golden test."""
        self._run_golden_test("python_add_field")

    def test_typescript_add_field(self):
        """TypeScript add_field golden test."""
        self._run_golden_test("typescript_add_field")

    def test_jsp_add_field(self):
        """JSP add_field golden test."""
        self._run_golden_test("jsp_add_field")

    def test_sql_add_field(self):
        """SQL add_field golden test."""
        self._run_golden_test("sql_add_field")

    def test_go_add_field(self):
        """Go add_field golden test."""
        self._run_golden_test("go_add_field")

    def test_csharp_add_field(self):
        """C# add_field golden test."""
        self._run_golden_test("csharp_add_field")

    def test_ruby_add_field(self):
        """Ruby add_field golden test."""
        self._run_golden_test("ruby_add_field")

    def test_kotlin_add_field(self):
        """Kotlin add_field golden test."""
        self._run_golden_test("kotlin_add_field")

    def test_rust_add_field(self):
        """Rust add_field golden test."""
        self._run_golden_test("rust_add_field")

    def test_php_add_field(self):
        """PHP add_field golden test."""
        self._run_golden_test("php_add_field")

    def test_perl_add_field(self):
        """Perl add_field golden test."""
        self._run_golden_test("perl_add_field")


def run_all_tests():
    """Run all conformance and golden tests."""
    print("=" * 60)
    print("WICKED-PATCH GENERATOR CONFORMANCE TESTS")
    print("=" * 60)
    print()

    # Import generators
    from generators import java_generator, python_generator, typescript_generator
    from generators import jsp_generator, sql_generator, go_generator, csharp_generator
    from generators import ruby_generator, kotlin_generator, rust_generator, php_generator, perl_generator

    # Run contract tests
    print("CONTRACT TESTS")
    print("-" * 40)

    samples = {
        ".java": "public class Test { private String field; }",
        ".py": "class Test:\n    field = Column(String)",
        ".ts": "export class Test { field: string; }",
        ".jsp": "<form:form><form:input path='field'/></form:form>",
        ".sql": "CREATE TABLE test (id INT);",
        ".go": "type Test struct { Field string }",
        ".cs": "public class Test { public string Field { get; set; } }",
        ".rb": "class Test < ApplicationRecord\n  attr_accessor :field\nend",
        ".kt": "data class Test(val field: String)",
        ".rs": "pub struct Test { pub field: String }",
        ".php": "class Test { private string $field; }",
        ".pm": "package Test;\nuse Moose;\nhas 'field' => (is => 'rw');\n1;",
    }

    all_passed = True
    for ext, generator_class in GeneratorRegistry.list_generators().items():
        sample = samples.get(ext, "")
        report = run_conformance_tests(generator_class, sample)
        status = "PASS" if report.passed else "FAIL"
        print(f"  {generator_class.name}: {status} ({report.pass_count}/{len(report.results)})")
        if not report.passed:
            all_passed = False
            for result in report.results:
                if not result.passed:
                    print(f"    - {result.test_name}: {result.message}")

    print()

    # Run golden tests
    print("GOLDEN TESTS")
    print("-" * 40)

    fixtures = load_fixtures()
    test_runner = TestGoldenOutput()

    for name in sorted(fixtures.keys()):
        try:
            test_runner._run_golden_test(name)
            print(f"  {name}: PASS")
        except Exception as e:
            print(f"  {name}: FAIL - {e}")
            all_passed = False

    print()
    print("=" * 60)
    if all_passed:
        print("ALL TESTS PASSED")
        return 0
    else:
        print("SOME TESTS FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(run_all_tests())
