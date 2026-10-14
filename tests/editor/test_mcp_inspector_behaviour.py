"""The MCP inspector pack's behaviour against a scripted host and a scripted MCP server (headless Chromium only).

The entry runs as a plain page; a harness in the same page plays the host over the editor's own MessagePort
(``host.hello``, ``mcp.state``, ``mcp.log``) and answers every ``mcp.request`` from a per-test fake server. The
conformance run covers the protocol cases with no session; these cover what a connected inspector does
(``refs/mcp-server.md``): pagination, list errors, a Restart's new log, argument forms, and calls only from a click.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
ENTRY = REPO / "packs" / "garden-mcp-inspector" / "editors" / "garden-mcp-inspector" / "index.html"


def _chromium_ready() -> bool:
    try:
        from playwright.sync_api import sync_playwright  # noqa: PLC0415
        with sync_playwright() as p:
            p.chromium.launch().close()
        return True
    except Exception:  # noqa: BLE001 — no driver or no browser: skipped, said so
        return False


pytestmark = pytest.mark.skipif(not _chromium_ready(), reason="needs playwright + chromium")

# The scripted host: one MessageChannel; the editor's requests land in __h.reqs, mcp.request is answered by
# __h.server(method, params) -> a JSON-RPC response ({result} | {error}), anything else is refused not_granted.
HARNESS = """(surface) => {
  const ch = new MessageChannel();
  const h = window.__h = { reqs: [], events: [], port: ch.port1, hold: false, held: [], server: () => ({ error: { code: -32601, message: 'none' } }) };
  h.flush = () => { h.hold = false; const xs = h.held.splice(0); for (const f of xs) f(); };
  ch.port1.onmessage = (e) => {
    const m = e.data;
    if (m && typeof m.type === 'string' && typeof m.id === 'string') {
      h.reqs.push({ type: m.type, payload: m.payload });
      if (m.type === 'mcp.request') {
        const resp = h.server(m.payload.method, m.payload.params);
        const answer = () => ch.port1.postMessage({ p: 'wicked.editor', v: 1, re: m.id, ok: true, payload: { response: resp, ms: 1, truncated: false } });
        if (h.hold) h.held.push(answer); else answer();
      } else {
        ch.port1.postMessage({ p: 'wicked.editor', v: 1, re: m.id, ok: false, error: { code: 'not_granted', message: 'scripted host' } });
      }
    } else if (m && typeof m.re === 'string') {
      h.events.push({ reply: m.re, payload: m.payload });
    } else if (m && typeof m.type === 'string') {
      h.events.push({ type: m.type, payload: m.payload });
    }
  };
  h.send = (type, payload, id) => ch.port1.postMessage(id ? { p: 'wicked.editor', v: 1, type, id, payload } : { p: 'wicked.editor', v: 1, type, payload });
  window.postMessage({ p: 'wicked.editor', v: 1, type: 'host.hello', payload: { protocol: 2, surface, size: surface === 'card' ? 'inline' : 'full',
    grants: ['artifact.read', 'mcp.session', 'ui.fullscreen'], theme: {} } }, '*', [ch.port2]);
}"""


@pytest.fixture()
def inspector():
    from playwright.sync_api import sync_playwright  # noqa: PLC0415

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1200, "height": 700})
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(ENTRY.as_uri())

        def start(server_js: str, surface: str = "full") -> None:
            page.evaluate(HARNESS, surface)
            page.evaluate(f"() => {{ window.__h.server = {server_js}; }}")

        def ready() -> None:
            page.evaluate("() => window.__h.send('mcp.state', { state: 'ready', server: { name: 'fake' }, protocolVersion: '2025-06-18' })")

        def mcp_calls(method: str | None = None) -> list:
            reqs = page.evaluate("() => window.__h.reqs")
            return [r["payload"] for r in reqs if r["type"] == "mcp.request" and (method is None or r["payload"]["method"] == method)]

        yield page, start, ready, mcp_calls
        assert errors == [], errors
        browser.close()


ECHO = {"name": "echo", "description": "Say it back", "inputSchema": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}}


def test_every_page_of_a_list_is_shown(inspector):
    page, start, ready, calls = inspector
    start("""(m, p) => m === 'tools/list' ? (p && p.cursor === 'c2' ? { result: { tools: [{ name: 'second' }] } }
              : { result: { tools: [{ name: 'first' }], nextCursor: 'c2' } }) : { result: { resources: [], prompts: [] } }""")
    ready()
    page.locator("button[data-item='second']").wait_for(timeout=5000)
    assert page.locator("#list button[data-item]").evaluate_all("bs => bs.map(b => b.dataset.item)") == ["first", "second"]
    assert [c.get("params") for c in calls("tools/list")] == [None, {"cursor": "c2"}]


def test_a_list_the_server_refuses_shows_its_error_not_an_empty_list(inspector):
    page, start, ready, _ = inspector
    start("""(m) => m === 'resources/list' ? { error: { code: -32601, message: 'method not found' } }
              : m === 'tools/list' ? { result: { tools: [] } } : { result: { prompts: [] } }""")
    ready()
    page.locator("nav button[data-tab='resources']").click()
    err = page.locator("#list li.err")
    err.wait_for(timeout=5000)
    assert err.inner_text() == "The server answered an error: method not found"


def test_a_restart_starts_the_log_over(inspector):
    page, start, ready, _ = inspector
    start("(m) => ({ result: { tools: [], resources: [], prompts: [] } })")
    ready()
    old = [{"seq": n, "at": "t", "dir": "out", "kind": "request", "method": "tools/list", "text": "{}"} for n in range(1, 101)]
    page.evaluate("(es) => window.__h.send('mcp.log', { entries: es })", old)
    page.evaluate("() => window.__h.send('mcp.state', { state: 'connecting' })")
    ready()
    page.evaluate("() => window.__h.send('mcp.log', { entries: [{ seq: 1, at: 't', dir: 'out', kind: 'request', method: 'ping', text: '{\"new\":1}' }] })")
    page.locator("nav button[data-tab='log']").click()
    page.locator("#log li").first.wait_for(timeout=5000)
    assert page.locator("#log li").count() == 1 and "ping" in page.locator("#log li").first.inner_text()


def test_a_call_leaves_only_from_a_click_and_its_result_is_shown_as_text(inspector):
    page, start, ready, calls = inspector
    start(f"""(m, p) => m === 'tools/list' ? {{ result: {{ tools: [{json.dumps(ECHO)}] }} }}
              : m === 'tools/call' ? {{ result: {{ content: [{{ type: 'text', text: '<b>' + p.arguments.text + '</b>' }}] }} }}
              : {{ result: {{ resources: [], prompts: [] }} }}""")
    ready()
    page.locator("button[data-item='echo']").click()
    page.wait_for_timeout(300)
    page.evaluate("() => window.__h.send('host.action', { id: 'refresh' }, 'a1')")
    page.wait_for_timeout(300)
    assert calls("tools/call") == []  # listing, picking a tool and the card action never call it
    page.locator("input[data-arg='text']").fill("hi")
    page.locator("button.primary").click()
    page.locator("#result:not([hidden])").wait_for(timeout=5000)
    assert calls("tools/call") == [{"method": "tools/call", "params": {"name": "echo", "arguments": {"text": "hi"}}}]
    assert "<b>hi</b>" in page.locator("#result").inner_text() and page.locator("#result b").count() == 0
    replies = [e for e in page.evaluate("() => window.__h.events") if e.get("reply") == "a1"]
    assert replies == [{"reply": "a1", "payload": {"handled": True, "status": "Listing again"}}]


def test_keys_beyond_the_fields_go_in_the_more_arguments_box(inspector):
    page, start, ready, calls = inspector
    tool = {"name": "auth", "inputSchema": {"type": "object", "properties": {"mode": {"type": "string"}},
                                             "additionalProperties": {"type": "string"}, "required": ["token"]}}
    start(f"""(m) => m === 'tools/list' ? {{ result: {{ tools: [{json.dumps(tool)}] }} }}
              : m === 'tools/call' ? {{ result: {{ content: [] }} }} : {{ result: {{ resources: [], prompts: [] }} }}""")
    ready()
    page.locator("button[data-item='auth']").click()
    more = page.locator("textarea[data-arg='+']")
    assert "needs token" in page.locator("label", has=more).inner_text()
    page.locator("input[data-arg='mode']").fill("fast")
    page.locator("button.primary").click()
    assert page.locator("p.err").inner_text() == "token is required"
    more.fill('{"mode": "x"}')
    page.locator("button.primary").click()
    assert page.locator("p.err").inner_text() == "mode is set twice"
    more.fill('{"token": "t1"}')
    page.locator("button.primary").click()
    page.locator("#result:not([hidden])").wait_for(timeout=5000)
    assert calls("tools/call")[-1]["params"]["arguments"] == {"mode": "fast", "token": "t1"}


def test_a_root_the_fields_cannot_express_gets_one_json_box(inspector):
    page, start, ready, calls = inspector
    tool = {"name": "union", "inputSchema": {"oneOf": [{"type": "object"}, {"type": "object", "properties": {"a": {"type": "number"}}}]}}
    start(f"""(m) => m === 'tools/list' ? {{ result: {{ tools: [{json.dumps(tool)}] }} }}
              : m === 'tools/call' ? {{ result: {{ content: [] }} }} : {{ result: {{ resources: [], prompts: [] }} }}""")
    ready()
    page.locator("button[data-item='union']").click()
    box = page.locator("textarea[data-arg='*']")
    box.fill("[1]")
    page.locator("button.primary").click()
    assert page.locator("p.err").inner_text() == "The arguments must be a JSON object"
    box.fill('{"a": 2}')
    page.locator("button.primary").click()
    page.locator("#result:not([hidden])").wait_for(timeout=5000)
    assert calls("tools/call")[-1]["params"]["arguments"] == {"a": 2}


def test_a_prompts_declared_arguments_are_asked_for(inspector):
    page, start, ready, calls = inspector
    prompt = {"name": "brief", "arguments": [{"name": "topic", "required": True}, {"name": "tone"}]}
    start(f"""(m) => m === 'prompts/list' ? {{ result: {{ prompts: [{json.dumps(prompt)}] }} }}
              : m === 'prompts/get' ? {{ result: {{ messages: [] }} }} : {{ result: {{ tools: [], resources: [] }} }}""")
    ready()
    page.locator("nav button[data-tab='prompts']").click()
    page.locator("button[data-item='brief']").click()
    page.locator("button.primary").click()
    assert page.locator("p.err").inner_text() == "topic is required"
    page.locator("input[data-arg='topic']").fill("garden")
    page.locator("button.primary").click()
    page.locator("#result:not([hidden])").wait_for(timeout=5000)
    assert calls("prompts/get")[-1]["params"] == {"name": "brief", "arguments": {"topic": "garden"}}


def test_a_reply_from_an_ended_connection_never_replaces_the_list(inspector):
    page, start, ready, _ = inspector
    start("(m) => m === 'tools/list' ? { result: { tools: [{ name: 'shown' }] } } : { result: { resources: [], prompts: [] } }")
    ready()
    page.locator("button[data-item='shown']").wait_for(timeout=5000)
    # A second listing is still in flight when the connection closes; its late answer must not replace the stale list.
    page.evaluate("""() => { window.__h.hold = true; window.__h.server = (m) => m === 'tools/list'
        ? { error: { code: -32000, message: 'gone' } } : { error: { code: -32000, message: 'gone' } }; }""")
    page.evaluate("() => window.__h.send('host.action', { id: 'refresh' }, 'a2')")
    page.wait_for_timeout(200)
    page.evaluate("() => window.__h.send('mcp.state', { state: 'closed' })")
    page.evaluate("() => window.__h.flush()")
    page.wait_for_timeout(300)
    assert page.locator("#status").get_attribute("data-stale") == "1"
    assert page.locator("button[data-item='shown']").count() == 1 and page.locator("#list li.err").count() == 0
    page.evaluate("() => { window.__h.server = (m) => m === 'tools/list' ? { result: { tools: [{ name: 'new' }] } } : { result: { resources: [], prompts: [] } }; }")
    ready()
    page.locator("button[data-item='new']").wait_for(timeout=5000)
    assert page.locator("button[data-item='shown']").count() == 0


def _tools(page, start, ready, tools_js: str) -> None:
    start(f"""(m, p) => m === 'tools/list' ? {{ result: {{ tools: {tools_js} }} }}
              : m === 'tools/call' ? {{ result: {{ content: [{{ type: 'text', text: 'done' }}] }} }} : {{ result: {{ resources: [], prompts: [] }} }}""")
    ready()


def test_a_required_value_is_asked_for_and_a_required_empty_string_is_sent(inspector):
    page, start, ready, calls = inspector
    tool = {"name": "t", "inputSchema": {"type": "object", "additionalProperties": False, "required": ["s", "n"],
                                          "properties": {"s": {"type": "string"}, "n": {"type": "integer"}}}}
    _tools(page, start, ready, json.dumps([tool]))
    page.locator("button[data-item='t']").click()
    page.locator("button.primary").click()
    assert page.locator("p.err").inner_text() == "n is required" and calls("tools/call") == []
    page.locator("input[data-arg='n']").fill("3")
    page.locator("button.primary").click()
    page.locator("#result:not([hidden])").wait_for(timeout=5000)
    assert calls("tools/call")[-1]["params"]["arguments"] == {"s": "", "n": 3}


def test_a_relisted_tool_with_another_schema_gets_a_new_form(inspector):
    page, start, ready, calls = inspector
    old = {"name": "t", "inputSchema": {"type": "object", "additionalProperties": False, "required": ["old"], "properties": {"old": {"type": "string"}}}}
    _tools(page, start, ready, json.dumps([old]))
    page.locator("button[data-item='t']").click()
    page.locator("input[data-arg='old']").fill("kept?")
    new = {"name": "t", "inputSchema": {"type": "object", "additionalProperties": False, "required": ["new"], "properties": {"new": {"type": "string"}}}}
    page.evaluate(f"() => {{ window.__h.server = (m) => m === 'tools/list' ? {{ result: {{ tools: {json.dumps([new])} }} }} : {{ result: {{ content: [], resources: [], prompts: [] }} }}; }}")
    page.evaluate("() => window.__h.send('host.action', { id: 'refresh' }, 'a3')")
    page.locator("input[data-arg='new']").wait_for(timeout=5000)
    assert page.locator("input[data-arg='old']").count() == 0


def test_a_late_call_reply_from_an_ended_connection_is_not_shown(inspector):
    page, start, ready, calls = inspector
    _tools(page, start, ready, json.dumps([ECHO]))
    page.locator("button[data-item='echo']").click()
    page.locator("input[data-arg='text']").fill("hi")
    page.evaluate("() => { window.__h.hold = true; }")
    page.locator("button.primary").click()
    page.wait_for_timeout(200)
    page.evaluate("() => window.__h.send('mcp.state', { state: 'closed' })")
    page.evaluate("() => window.__h.send('mcp.state', { state: 'connecting' })")
    ready()
    page.evaluate("() => window.__h.flush()")
    page.wait_for_timeout(500)
    assert len(calls("tools/call")) == 1 and page.locator("#result:not([hidden])").count() == 0


def test_a_blank_required_string_can_come_from_more_arguments_with_its_newlines(inspector):
    page, start, ready, calls = inspector
    tool = {"name": "src", "inputSchema": {"type": "object", "additionalProperties": False, "required": ["code"], "properties": {"code": {"type": "string"}}}}
    _tools(page, start, ready, json.dumps([tool]))
    page.locator("button[data-item='src']").click()
    page.locator("textarea[data-arg='+']").fill(json.dumps({"code": "line 1\nline 2"}))
    page.locator("button.primary").click()
    page.locator("#result:not([hidden])").wait_for(timeout=5000)
    assert calls("tools/call")[-1]["params"]["arguments"] == {"code": "line 1\nline 2"}


def test_two_relists_whose_answers_cross_keep_the_newer_one(inspector):
    page, start, ready, _ = inspector
    old = {"name": "t", "inputSchema": {"type": "object", "additionalProperties": False, "properties": {"old": {"type": "string"}}}}
    new = {"name": "t", "inputSchema": {"type": "object", "additionalProperties": False, "properties": {"new": {"type": "string"}}}}
    _tools(page, start, ready, json.dumps([old]))
    page.locator("button[data-item='t']").click()
    page.evaluate("() => { window.__h.hold = true; }")  # listing A asks now and is answered (old) only later
    page.evaluate("() => window.__h.send('host.action', { id: 'refresh' }, 'a4')")
    page.wait_for_timeout(300)
    page.evaluate(f"() => {{ window.__h.hold = false; window.__h.server = (m) => m === 'tools/list' ? {{ result: {{ tools: {json.dumps([new])} }} }} : {{ result: {{ resources: [], prompts: [] }} }}; }}")
    page.evaluate("() => window.__h.send('host.action', { id: 'refresh' }, 'a5')")  # listing B: answered at once (new)
    page.locator("input[data-arg='new']").wait_for(timeout=5000)
    page.evaluate("() => window.__h.flush()")  # A's old answers land last
    page.wait_for_timeout(500)
    assert page.locator("input[data-arg='new']").count() == 1 and page.locator("input[data-arg='old']").count() == 0
