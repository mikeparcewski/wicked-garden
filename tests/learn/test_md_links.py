"""Link extraction contracts; adapted examples cite CommonMark 0.31.2 or GFM."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
import time
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "learn" / "_md_links.py"
_spec = importlib.util.spec_from_file_location("learn_md_links_tests", SCRIPT)
md = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = md
_spec.loader.exec_module(md)


def destinations(text):
    return [link.destination for link in md.rendered_links(text)]


def test_normalise_line_endings_and_nul():
    assert md.normalise("a\rb\r\nc\nd\0") == "a\nb\nc\nd\ufffd"


@pytest.mark.parametrize("source", [
    # CommonMark examples 342 and 525: code consumes the apparent closing bracket.
    "[not a `citation](/hidden`)",
    "[citation`](/hidden)`",
    # CommonMark example 343: a code span starts before the apparent HTML tag.
    '`<a href="`">`',
    # CommonMark example 345: a code span starts before the apparent autolink.
    "`<https://example.org/`suffix>`",
    # CommonMark example 339: only equal-length backtick strings close code.
    "`` [citation](/hidden) ` still code ``",
])
def test_code_precedence_hides_apparent_links(source):
    assert md.rendered_links(source) == []


def test_html_tag_precedes_later_backtick():
    # CommonMark example 344: the backtick inside an HTML attribute is literal.
    links = md.rendered_links('<a href="`">`')
    assert [(link.kind, link.destination) for link in links] == [("html", "`")]


def test_autolink_precedes_later_backtick():
    # CommonMark example 346: the first opener wins, read left to right.
    links = md.rendered_links("<https://example.org/`path>`")
    assert [(link.kind, link.destination) for link in links] == [
        ("autolink", "https://example.org/`path")]


def test_unmatched_backticks_do_not_hide_links():
    # CommonMark example 347: unmatched strings are ordinary text.
    assert destinations("``before [citation](/visible)`") == ["/visible"]


@pytest.mark.parametrize(("source", "expected"), [
    # CommonMark examples 483–486: destinations can be relative or empty.
    ("[citation](/relative)", "/relative"),
    ("[](./report.md)", "./report.md"),
    ("[citation]()", ""),
    ("[citation](<>)", ""),
    # CommonMark examples 489, 492 and 496: angle spaces / balanced parentheses.
    ("[citation](</two words>)", "/two words"),
    ("[citation](</a)b>)", "/a)b"),
    ("[citation](/one(two(three)))", "/one(two(three))"),
    # CommonMark examples 495, 502 and 503: decode escapes/entities, not percent escapes.
    (r"[citation](/\(one\))", "/(one)"),
    (r"[citation](/one\z)", r"/one\z"),
    ("[citation](/a%20b&auml;)", "/a%20bä"),
    # CommonMark example 505: all three title delimiters.
    ('[citation](/target "a title")', "/target"),
    ("[citation](/target 'a title')", "/target"),
    ("[citation](/target (a title))", "/target"),
])
def test_inline_destinations(source, expected):
    links = md.rendered_links(source)
    assert [(link.kind, link.destination, link.image) for link in links] == [
        ("inline", expected, False)]


@pytest.mark.parametrize("source", [
    # CommonMark examples 488, 490, 491 and 497: malformed destinations are text.
    "[citation](/two words)",
    "[citation](/two\nwords)",
    "[citation](</two\nwords>)",
    "[citation](/one(two(three))",
    # CommonMark example 508: titles cannot contain an unescaped matching quote.
    '[citation](/target "title "inside" title")',
])
def test_invalid_inline_destinations_are_not_links(source):
    assert md.rendered_links(source) == []


@pytest.mark.parametrize(("raw", "decoded"), [
    # CommonMark examples 28–30 and 503: only valid, semicolon-terminated references.
    ("/a&amp;b", "/a&b"),
    ("/a&#58;b", "/a:b"),
    ("/a&#x3a;b", "/a:b"),
    ("/a&#0;b", "/a\ufffdb"),
    ("/a&copy", "/a&copy"),
    ("/a&MadeUpEntity;", "/a&MadeUpEntity;"),
    ("/a&#12345678;b", "/a&#12345678;b"),
])
def test_commonmark_entity_syntax_in_destinations(raw, decoded):
    links = md.rendered_links(f"[citation]({raw})")
    assert [(link.raw, link.destination) for link in links] == [(raw, decoded)]


def test_escaped_or_entity_brackets_do_not_create_link_structure():
    # CommonMark examples 563 and 37: decoded punctuation cannot become syntax.
    assert md.rendered_links(r"\[citation](/hidden)") == []
    assert md.rendered_links("&#91;citation](/hidden)") == []


def test_nested_link_deactivates_outer_opener():
    # CommonMark example 518: an active inner link prevents an outer link.
    assert destinations("[outer [inner](/inner)](/outer)") == ["/inner"]


def test_image_can_be_inside_a_link():
    # CommonMark example 517: images do not deactivate link openers.
    links = md.rendered_links("[![chart](/chart.png)](/report)")
    assert sorted((link.destination, link.image) for link in links) == [
        ("/chart.png", True), ("/report", False)]


def test_html_and_autolinks_bind_before_link_brackets():
    # CommonMark examples 524 and 526: brackets inside an HTML tag / autolink are literal.
    assert md.rendered_links('[outer <tag attr="](/hidden)">') == []
    assert destinations("[outer<https://example.org/?q=](/hidden)>") == [
        "https://example.org/?q=](/hidden)"]


@pytest.mark.parametrize("use", ["[label][ref]", "[ref][]", "[ref]"])
def test_full_collapsed_and_shortcut_references(use):
    # CommonMark examples 527, 553 and 557: the three reference forms.
    links = md.rendered_links(use + "\n\n[ref]: </target>\n")
    assert [(link.kind, link.destination) for link in links] == [("reference", "/target")]


def test_first_reference_definition_wins():
    # CommonMark example 204: duplicate definitions cannot replace the first.
    assert destinations("[ref]\n\n[ref]: /first\n[ref]: /second\n") == ["/first"]


def test_reference_labels_use_unicode_casefold_and_whitespace_collapse():
    # CommonMark examples 540 and 541, combined with a multiline definition label.
    assert destinations("[label][STRASSE multi word]\n\n[Straße\n multi\tword]: /target\n") == [
        "/target"]


def test_escaped_closing_bracket_in_reference_label():
    # CommonMark example 194: an escaped bracket belongs to the label.
    assert destinations("[label][ref\\]]\n\n[ref\\]]: /target\n") == ["/target"]


def test_reference_matching_does_not_decode_backslash_escapes():
    # CommonMark example 545: labels compare source spelling after case/space folding.
    assert md.rendered_links("[label][ref\\!]\n\n[ref!]: /hidden\n") == []


@pytest.mark.parametrize(("length", "expected"), [(999, ["/target"]), (1000, [])])
def test_reference_label_length_limit(length, expected):
    label = "x" * length
    assert destinations(f"[{label}]\n\n[{label}]: /target\n") == expected


@pytest.mark.parametrize("title", ['"title"', "'title'", "(title)"])
def test_reference_destination_and_title_may_start_on_later_lines(title):
    # CommonMark examples 193 and 195: destination and title can occupy separate lines.
    assert destinations("[ref]:\n  </target>\n  " + title + "\n\n[ref]\n") == ["/target"]


def test_definitions_only_at_start_of_paragraph():
    # CommonMark example 213: a definition cannot interrupt prose.
    assert md.rendered_links("Paragraph\n[ref]: /hidden\n\n[ref]\n") == []


def test_definition_after_atx_heading_is_global():
    # CommonMark example 214: a heading ends before a following definition.
    assert destinations("# [ref]\n[ref]: /target\n> following paragraph\n") == ["/target"]


def test_unused_definition_is_not_a_rendered_link():
    # CommonMark example 207: a definition itself emits no href.
    assert md.rendered_links("[ref]: /target\n") == []


def test_empty_angle_reference_destination():
    # CommonMark example 200: angle form permits the empty destination.
    assert destinations("[ref]: <>\n\n[ref]\n") == [""]


def test_unicode_whitespace_is_allowed_inside_bare_destination():
    # CommonMark example 507: NBSP is not the ASCII separator before a title.
    assert destinations('[citation](/target\u00a0"title")') == ['/target\u00a0"title"']


def test_unclosed_following_bracket_does_not_suppress_shortcut_reference():
    assert destinations("[ref][unclosed\n\n[ref]: /target\n") == ["/target"]


def test_ordered_list_sibling_can_define_reference():
    # CommonMark §5.2: only a new ordered list's paragraph interruption requires 1.
    assert destinations("[ref]\n\n1. first\n2. [ref]: </target>\n") == ["/target"]


def test_image_reference_uses_case_insensitive_matching():
    # CommonMark examples 572 and 591: images share destination/reference syntax.
    links = md.rendered_links("![CHART]\n\n[chart]: </chart.png>\n")
    assert [(link.kind, link.destination, link.image) for link in links] == [
        ("reference", "/chart.png", True)]


@pytest.mark.parametrize(("source", "kind", "destination"), [
    # CommonMark examples 594–598: web and arbitrary 2–32 character schemes.
    ("<http://example.org>", "autolink", "http://example.org"),
    ("<IRC://example.org:2233/channel>", "autolink", "IRC://example.org:2233/channel"),
    ("<a+b+c:value>", "autolink", "a+b+c:value"),
    ("<MAILTO:NAME@EXAMPLE.ORG>", "autolink", "MAILTO:NAME@EXAMPLE.ORG"),
    # CommonMark examples 604–605: email autolinks add mailto, including plus addresses.
    ("<name@example.org>", "email-autolink", "mailto:name@example.org"),
    ("<name+tag@Example.org>", "email-autolink", "mailto:name+tag@Example.org"),
])
def test_autolink_destinations(source, kind, destination):
    links = md.rendered_links(source)
    assert [(link.kind, link.destination) for link in links] == [(kind, destination)]


def test_autolink_backslashes_remain_literal():
    # CommonMark example 603: URI autolinks do not interpret backslash escapes.
    source = r"<https://example.org/\[\>"
    assert destinations(source) == [source[1:-1]]


def test_commonmark_autolink_decodes_entities_but_not_backslash_escapes():
    links = md.rendered_links(r"<https://example.org/a&amp;b\*c>")
    assert [(link.raw, link.destination) for link in links] == [
        (r"https://example.org/a&amp;b\*c", r"https://example.org/a&b\*c")]


def test_raw_html_custom_tag_and_attribute_entities():
    # CommonMark example 617: arbitrary tag names, not a hand-picked HTML tag list.
    links = md.rendered_links('Text <custom-widget src="/image?a=1&amp;b=2" />')
    assert [(link.kind, link.raw, link.destination) for link in links] == [
        ("html", "/image?a=1&amp;b=2", "/image?a=1&b=2")]


@pytest.mark.parametrize("attribute", [
    "href", "src", "action", "formaction", "data", "poster", "cite",
])
@pytest.mark.parametrize("quotes", ['"', "'", ""])
def test_raw_html_reads_each_simple_link_attribute(attribute, quotes):
    links = md.rendered_links(f"Text <custom-tag {attribute}={quotes}/target{quotes}>")
    assert [(link.kind, link.destination) for link in links] == [("html", "/target")]


@pytest.mark.parametrize("source", [
    # CommonMark §4.6 HTML block types 1 through 7 respectively.
    '<script>\n<tag src="/target">\n</script>',
    '<!-- comment\n-->\n<tag src="/target">',
    '<?instruction\n?>\n<tag src="/target">',
    '<!DECLARATION\n>\n<tag src="/target">',
    '<![CDATA[raw\n]]>\n<tag src="/target">',
    '<div>\n<tag src="/target">\n</div>',
    '<custom-element>\n<tag src="/target">\n</custom-element>',
])
def test_html_blocks_report_attributes(source):
    assert ("html", "/target") in [
        (link.kind, link.destination) for link in md.rendered_links(source)]


@pytest.mark.parametrize("source", [
    # CommonMark §6.6: raw HTML constructs consume their literal inline content.
    'Text <!-- [hidden](/hidden) -->',
    'Text <?instruction [hidden](/hidden) ?>',
    'Text <!DECLARATION [hidden](/hidden)>',
    'Text <![CDATA[ [hidden](/hidden) ]]>',
])
def test_inline_raw_html_is_not_markdown(source):
    assert md.rendered_links(source) == []


@pytest.mark.parametrize("source", [
    "```markdown\n[citation](/hidden)\n```\n",
    "~~~~ info\n[citation](/hidden)\n~~~~\n",
    "    [citation](/hidden)\n",
    "> ```\n> [citation](/hidden)\n> ```\n",
    "- ```\n  [citation](/hidden)\n  ```\n",
])
def test_code_blocks_exclude_links(source):
    assert md.rendered_links(source) == []


def test_unindented_blank_line_does_not_end_a_fence_inside_a_list():
    source = '- ```\n\n  [hidden](/hidden)\n  ```\n\n[shown](/shown)'
    assert destinations(source) == ["/shown"]


def test_container_markers_inside_a_fence_cannot_close_it():
    source = '- ```\n  - ```\n  ```\n\n[shown](/shown)'
    assert destinations(source) == ["/shown"]


@pytest.mark.parametrize("blank", ["", "\n"])
def test_partial_container_tab_cannot_turn_indented_code_into_a_fence(blank):
    source = '- paragraph\n' + blank + '\t   ```\n\n[shown](/shown)'
    assert destinations(source) == ["/shown"]


def test_inline_tabs_in_destinations_are_not_expanded_by_container_parsing():
    source = '> [shown](</one\ttwo>)'
    link, = md.rendered_links(source)
    assert link.destination == '/one\ttwo'
    assert link.raw == source[link.start:link.end] == '/one\ttwo'


@pytest.mark.parametrize("source", [
    "# [citation](/target)\n",
    "[citation](/target)\n===\n",
    "> - [citation](/target)\n",
    "> paragraph\n[citation](/target)\n",
    "- paragraph\n[citation](/target)\n",
    "Paragraph\n    [citation](/target)\n",
    "***\n[citation](/target)\n",
])
def test_headings_containers_and_lazy_paragraph_continuation(source):
    assert destinations(source) == ["/target"]


@pytest.mark.parametrize("ending", ["\n", "\r", "\r\n"])
def test_reference_definitions_accept_all_line_endings(ending):
    source = ending.join(["[label][multi word]", "", "[multi", "word]: /target", ""])
    assert destinations(source) == ["/target"]


def test_raw_spans_use_normalised_source_offsets():
    source = "Title\r\n\r\n> [citation](https://example.org/a&amp;b)\rnext\0"
    normalised = md.normalise(source)
    links = md.rendered_links(source)
    assert len(links) == 1
    link = links[0]
    assert normalised[link.start:link.end] == link.raw == "https://example.org/a&amp;b"
    assert link.destination == "https://example.org/a&b"


@pytest.mark.parametrize(("source", "raw", "destination"), [
    # GFM examples 622–624: www prefix and trailing punctuation.
    ("www.example.org", "www.example.org", "http://www.example.org"),
    ("Visit www.example.org/a.b.!", "www.example.org/a.b", "http://www.example.org/a.b"),
    # GFM example 625: remove only unmatched trailing closing parentheses.
    ("(www.example.org/a(b)))", "www.example.org/a(b)", "http://www.example.org/a(b)"),
    # GFM example 627: a trailing entity-shaped sequence is excluded.
    ("www.example.org/a&copy;", "www.example.org/a", "http://www.example.org/a"),
    # GFM example 629: bare http(s) URLs, preserving balanced parentheses.
    ("https://example.org/a(b).", "https://example.org/a(b)", "https://example.org/a(b)"),
    # GFM examples 630–632: extended email and trailing period.
    ("name+tag@example.org.", "name+tag@example.org", "mailto:name+tag@example.org"),
])
def test_gfm_extended_autolinks(source, raw, destination):
    links = md.rendered_links(source)
    assert [(link.kind, link.raw, link.destination) for link in links] == [
        ("gfm-autolink", raw, destination)]


@pytest.mark.parametrize(("source", "expected"), [
    # GFM §6.9 permits underscores in extended email domains, except at the end.
    ("name@department_team.example.org", ["mailto:name@department_team.example.org"]),
    ("name@department.example_", []),
    ("name@department.example-", []),
    ("www.team_name.org@example.org", ["mailto:www.team_name.org@example.org"]),
    # The final two URL domain labels cannot contain underscores.
    ("www.team_name.example.org", ["http://www.team_name.example.org"]),
    ("www.example_name.org", []),
    ("https://example.org_", []),
    # URL autolinks require a domain and an allowed preceding character.
    ("www./path", []),
    ("prefix:https://example.org", []),
    ("(https://example.org/a.)", ["https://example.org/a"]),
    # GFM URL autolinks consume the source chunk without decoding entities/escapes.
    ("https://example.org/a&amp;b", ["https://example.org/a&amp;b"]),
    (r"www.example.org/a\*b", [r"http://www.example.org/a\*b"]),
    ("https://localhost/path", ["https://localhost/path"]),
    ("www.例子.公司", ["http://www.例子.公司"]),
])
def test_gfm_domains_boundaries_and_decoding(source, expected):
    assert [link.destination for link in md.rendered_links(source)
            if link.kind == "gfm-autolink"] == expected


@pytest.mark.parametrize(("source", "destination"), [
    ("someone&#64;example.org", "mailto:someone@example.org"),
    ("someone&commat;example.org", "mailto:someone@example.org"),
    ("someone@example&#46;org", "mailto:someone@example.org"),
    (r"some\+one@example.org", "mailto:some+one@example.org"),
])
def test_extended_email_detection_runs_after_text_decoding(source, destination):
    links = md.rendered_links(source)
    assert [(link.kind, link.raw, link.destination) for link in links] == [
        ("gfm-autolink", source, destination)]
    assert [(link.start, link.end) for link in links] == [(0, len(source))]


def test_decoded_email_is_not_extracted_inside_a_raw_gfm_url():
    source = "https://example.org/someone&commat;example.org"
    assert [(link.raw, link.destination) for link in md.rendered_links(source)] == [(source, source)]


@pytest.mark.parametrize("source", [
    "`www.example.org https://example.org name@example.org`",
    '[www.example.org https://example.org name@example.org](/target)',
    '<tag title="www.example.org https://example.org name@example.org">',
])
def test_gfm_autolinks_do_not_run_inside_code_html_or_links(source):
    assert all(link.kind != "gfm-autolink" for link in md.rendered_links(source))


def test_code_opener_before_fake_angle_link_does_not_hide_real_link():
    source = "`<https://logged.invalid/`[t](https://unlogged.invalid/x)>"
    assert [(link.kind, link.destination) for link in md.rendered_links(source)] == [
        ("inline", "https://unlogged.invalid/x")]


@pytest.mark.parametrize("label", ["multi\nline", r"escaped\]label"])
def test_issue_reference_label_bypasses_are_read(label):
    source = f"[t][{label}]\n\n[{label}]: /unlogged\n"
    assert [(link.kind, link.destination) for link in md.rendered_links(source)] == [
        ("reference", "/unlogged")]


def test_issue_cr_only_reference_bypass_is_read():
    assert destinations("paragraph\r\r[ref]: /unlogged\r\r[t][ref]\r") == ["/unlogged"]


def test_issue_email_autolink_bypass_is_read():
    assert [(link.kind, link.destination) for link in md.rendered_links("<someone@example.org>")] == [
        ("email-autolink", "mailto:someone@example.org")]


def test_escaped_first_backtick_leaves_a_shorter_code_opener():
    # CommonMark §6.1: backslash escapes apply outside code, not inside it.
    assert destinations(r"\``[hidden](/hidden)` [shown](/shown)") == ["/shown"]


def test_multiline_html_attribute_raw_span_includes_source_container_markers():
    source = '> <tag href="/one\n> /two">\n'
    link, = md.rendered_links(source)
    assert link.raw == source[link.start:link.end] == "/one\n> /two"
    assert link.destination == "/one\n/two"


def test_browser_repaired_html_block_attributes_are_reported_conservatively():
    link, = md.rendered_links('<form\n@ action="/target">')
    assert (link.kind, link.destination) == ("html", "/target")


def test_short_inline_html_comment_does_not_swallow_later_links():
    # CommonMark §6.6 includes both short comment forms.
    assert destinations('Text <!--> [one](/one) <!---> [two](/two) -->') == ["/one", "/two"]


def test_unmatched_brackets_are_part_of_an_extended_url_path():
    assert destinations("www.example.org/a[foo]") == ["http://www.example.org/a[foo]"]


def test_reference_in_a_later_ordered_list_item_starts_a_new_paragraph():
    assert destinations('[ref]\n\n1. first\n2. [ref]: /target\n') == ["/target"]


def test_repeated_references_to_a_long_destination_are_bounded():
    url = 'https://example.org/' + 'x' * 32_000
    source = '[ref]: <' + url + '>\n\n' + '[ref] ' * 20_000
    started = time.monotonic()
    links = md.rendered_links(source)
    assert len(links) == 20_000
    assert links[0].destination == links[-1].destination == url
    assert time.monotonic() - started < 3


@pytest.mark.parametrize("prefix", [
    "[x](" * 100_000,
    "[" * 250_000 + "]" * 250_000,
    "> " * 250_000,
    "<tag " * 100_000,
    "www." * 125_000 + "bad_name.invalid",
    "&amp;" + "a" * 500_000,
    "Text " + "<!--" * 125_000,
    "Text " + "<![CDATA[" * 55_555,
    "Text " + "<a href='" * 55_555,
])
def test_adversarial_half_megabyte_is_bounded(prefix):
    source = prefix + "\n\n[citation](https://example.org/visible)\n"
    started = time.monotonic()
    links = md.rendered_links(source)
    elapsed = time.monotonic() - started
    assert any(link.destination == "https://example.org/visible" for link in links)
    assert elapsed < 3, f"link reading took {elapsed:.3f}s"


def test_review_02_del_cannot_hide_an_inner_markdown_link():
    source = "<https://example.org/terms#\x7f[x](/evil)>"
    assert "/evil" in destinations(source)
    assert all(link.kind != "autolink" for link in md.rendered_links(source))


def test_review_03_nbsp_is_a_nonempty_reference_label():
    assert destinations("[\u00a0]: /evil\n\n[\u00a0]") == ["/evil"]


def test_review_03_unicode_space_does_not_merge_distinct_labels():
    source = "[a b]: /space\n[a\u00a0b]: /nbsp\n\n[a\u00a0b] [a b]"
    assert destinations(source) == ["/nbsp", "/space"]


def test_review_04_only_space_and_tab_can_follow_a_closing_fence():
    assert destinations("~~~\ncode\n~~~\u00a0\n~~~\n\n[x](/evil)") == ["/evil"]


def test_review_05_any_raw_html_end_tag_closes_type_one():
    assert destinations("<pre></style>\n[x](/evil)\n</pre>") == ["/evil"]


def test_review_06_lowercase_declaration_ends_its_block():
    assert destinations("<!a> `\n[x](/evil) `") == ["/evil"]


@pytest.mark.parametrize("tag", ["pre", "script", "style", "textarea"])
def test_review_07_raw_opening_tags_are_excluded_from_type_seven(tag):
    assert destinations(f"<{tag}/>\n[x](/evil)") == ["/evil"]


def test_review_08_unicode_casefold_cannot_create_an_html_block():
    assert destinations("<d\u0130v>\n[x](/evil)") == ["/evil"]


def test_review_08_long_s_cannot_create_a_raw_tag_or_crash():
    assert md.rendered_links("<\u017ftyle>") == []


def test_review_09_ordered_list_interruption_compares_numeric_start():
    assert destinations("paragraph\n01. [r]: /evil\n\n[r]") == ["/evil"]


def test_review_12_html_attribute_whitespace_includes_form_feed():
    assert destinations("<div>\n<a href\f=//evil.invalid>open</a>\n</div>") == ["//evil.invalid"]


@pytest.mark.parametrize("source", [
    pytest.param(("- " * 100_000) + "x", id="thematic-suffix"),
    pytest.param("p\n" + ("+ " * 100_000) + "x\n", id="line-end-copy"),
])
def test_review_14_nested_list_prefixes_are_linear(source):
    started = time.monotonic()
    assert md.rendered_links(source) == []
    elapsed = time.monotonic() - started
    assert elapsed < 3, f"nested list reading took {elapsed:.3f}s"


@pytest.mark.parametrize(("reference", "character"), [
    ("&#128;", "\x80"),
    ("&#127;", "\x7f"),
    ("&#xFDD0;", "\ufdd0"),
    ("&#0;", "\ufffd"),
    ("&#xD800;", "\ufffd"),
    ("&#x110000;", "\ufffd"),
])
def test_review_15_numeric_references_use_commonmark_scalars(reference, character):
    assert destinations(f"[x](/a{reference}b)") == [f"/a{character}b"]


def test_review_16_html_attribute_entities_respect_attribute_context():
    assert destinations('<a href="/?x=&copycat">') == ["/?x=&copycat"]


@pytest.mark.parametrize("source", [
    "xmpp:someone@example.org",
    "xmpp:someone&commat;example.org",
])
def test_review_17_protocol_email_preserves_scheme_and_span(source):
    link, = md.rendered_links(source)
    assert link.destination == "xmpp:someone@example.org"
    assert link.raw == source
    assert (link.start, link.end) == (0, len(source))


@pytest.mark.parametrize("source", ["www.example.org/a)&copy;", "www.example.org/a!&copy;"])
def test_review_18_entity_removal_resumes_autolink_trimming(source):
    assert destinations(source) == ["http://www.example.org/a"]


def test_round2_deep_lists_followed_by_blank_lines_are_linear():
    # Keep the quadratic baseline bounded too; the child measures parsing alone.
    program = """
import sys
import time
sys.path.insert(0, sys.argv[1])
import _md_links as md
source = ("- " * 100_000) + "x\\n" + ("\\n" * 100_000)
started = time.monotonic()
assert md.rendered_links(source) == []
elapsed = time.monotonic() - started
assert elapsed < 3, f"nested lists and blank lines took {elapsed:.3f}s"
"""
    subprocess.run([sys.executable, "-c", program, str(SCRIPT.parent)],
                   check=True, capture_output=True, text=True, timeout=4)


def test_round2_new_quote_indented_code_flushes_outer_paragraph():
    source = "[C1] [C2] [C3]\n>     `\n> [x](/evil)\n> `\n"
    assert destinations(source) == ["/evil"]


def test_round2_new_quote_resets_ordered_list_interruption_context():
    source = "[C1] [C2] [C3]\n> 2. [r]: /evil\n\n[t][r]\n"
    assert destinations(source) == ["/evil"]


@pytest.mark.parametrize("prefix", ["- ", "+ ", "* ", "1. ", "1) "])
def test_round2_new_list_item_resets_ordered_list_interruption_context(prefix):
    source = "paragraph\n" + prefix + "2. [r]: /evil\n\n[t][r]\n"
    assert destinations(source) == ["/evil"]


@pytest.mark.parametrize("source", [
    "> - ```\n\n[shown](/shown)\n",
    "- > ```\n\n[shown](/shown)\n",
    "> - ```\n>\n>   [hidden](/hidden)\n>   ```\n\n[shown](/shown)\n",
])
def test_round2_blank_list_continuation_respects_quote_boundaries(source):
    assert destinations(source) == ["/shown"]


def test_read_reports_the_source_spans_of_code():
    text = "a `x<y>` b\n\n```\n<?xml?>\n```\n\n    pkg@1.2.3\n\n> ``q@r.st``\n"
    code: list = []
    md._read(text, code)
    covered = "".join(text[a:b] for a, b in sorted(code))
    for piece in ("`x<y>`", "<?xml?>", "pkg@1.2.3", "``q@r.st``"):
        assert piece in covered, (piece, code)
    assert "a `" not in covered and " b" not in covered
    # a paragraph continuation line indented four spaces is paragraph text, not code
    code = []
    md._read("para\n    <?xml?>\n", code)
    assert code == []
