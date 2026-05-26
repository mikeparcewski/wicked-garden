"""
Conformance (contract) tests for wicked-patch generators.

Each registered generator is run against the generator contract for every
supported language. (Golden-output tests were removed — they loaded a
`fixtures/` directory that was never created; see #879.)

Usage:
    python test_conformance.py          # standalone runner
    pytest test_conformance.py -v       # via pytest
    pytest test_conformance.py -k java  # one generator
"""

import sys
from pathlib import Path

# Make the patch package + this tests dir importable regardless of the cwd
# pytest collects from, so `generators` and `generator_contract` resolve
# whether this runs from here or from the repo root.
_PATCH_DIR = Path(__file__).resolve().parent.parent
for _p in (str(_PATCH_DIR), str(_PATCH_DIR / "tests")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from generators import GeneratorRegistry
from generator_contract import run_conformance_tests


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
        from generators.jsp_generator import JspGenerator

        sample = """
<form:form modelAttribute="entity">
    <form:input path="existingField" />
</form:form>
"""
        report = run_conformance_tests(JspGenerator, sample)
        assert report.passed, report.summary()

    def test_sql_generator_contract(self):
        """SQL generator passes all contract tests."""
        from generators.sql_generator import SqlGenerator

        sample = """
CREATE TABLE test_table (
    id INTEGER PRIMARY KEY
);
"""
        report = run_conformance_tests(SqlGenerator, sample)
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


def run_all_tests():
    """Run all generator contract tests."""
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
    print("=" * 60)
    if all_passed:
        print("ALL TESTS PASSED")
        return 0
    else:
        print("SOME TESTS FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(run_all_tests())
