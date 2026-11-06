"""The engine-run demo recorder (DES-DEMO-RECORD-001, wicked-core#1249).

The unit half (the storyline-as-data checks, the request policy) runs anywhere Node does. The end-to-end half
records a fixture app with `demo-record.mjs record` / `probe` exactly as the engine's Tool runs it (minus the OS
jail, which wicked-core's own tests arm); it needs ffmpeg, python3 and the demo deps (Playwright in the garden
cache) and is skipped without them.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
DEMO = ROOT / "scripts" / "demo"
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "demo_record_app"

needs_node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")


def _node(script: str) -> str:
    out = subprocess.run(["node", "--input-type=module", "-e", script], cwd=DEMO, capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    return out.stdout


def _check(storyline: dict, chapters: list, launch: str = "/app", content_only: bool = False) -> dict:
    """{ok} or {code, where} from storyline-data.mjs checkStoryline."""
    return json.loads(_node(
        "import { checkStoryline } from './storyline-data.mjs';"
        f"const s = {json.dumps(storyline)}, c = {json.dumps(chapters)};"
        "try { checkStoryline(s, c, { appOrigin: 'http://127.0.0.1:7721', launchPath: " + json.dumps(launch)
        + f", contentOnly: {json.dumps(content_only)} }});"
        " console.log(JSON.stringify({ ok: true })); }"
        "catch (e) { console.log(JSON.stringify({ code: e.code, where: e.where, msg: e.message })); }"
    ))


def _story(steps: list, key: str = "01-a") -> tuple[dict, list]:
    return ({"title": "t", "ready": {"role": "heading", "name": "Board"}, "segments": [{"key": key, "title": "A", "steps": steps}]},
            [{"key": key, "title": "A"}])


@needs_node
def test_a_storyline_that_navigates_out_of_the_launch_path_is_refused():
    assert _check(*_story([{"go": {"path": "/app/details"}}]))["ok"]
    for bad in ("/api/v1/runs", "/apps-other", "//evil.example/x", "/app/../api/v1/runs"):
        got = _check(*_story([{"go": {"path": bad}}]))
        assert got.get("code") == "storyline_refused", (bad, got)
        assert got["where"].endswith(".go.path"), got


@needs_node
def test_a_path_that_could_break_out_of_an_attribute_is_refused():
    for bad in ('/app/"><script>x</script>', "/app/x'y", "/app/<b>", "/app/\u0007"):
        assert _check(*_story([{"go": {"path": bad}}])).get("code") == "storyline_refused", bad


@needs_node
def test_keys_fit_the_import_limit_and_match_the_chapter_plan():
    long_key = "a" * 49
    assert _check(*_story([{"hold": {"ms": 10}}], key=long_key)).get("code") == "storyline_refused"
    assert _check(*_story([{"hold": {"ms": 10}}], key="a" * 48))["ok"]
    story, _ = _story([{"hold": {"ms": 10}}])
    got = _check(story, [{"key": "02-other", "title": "B"}])
    assert got.get("where") == "storyline.segments" and "chapters.json" in got["msg"], got


@needs_node
def test_the_step_language_is_closed_and_bounded():
    assert _check(*_story([{"eval": {"code": "fetch('/api/v1/runs', {method: 'POST'})"}}])).get("code") == "storyline_refused"
    assert _check(*_story([{"hold": {"ms": 30_001}}])).get("code") == "storyline_refused"
    assert _check(*_story([{"card": {"title": "x", "ms": 100, "html": "<script>"}}])).get("code") == "storyline_refused"
    nested = {"time": {"label": "a", "steps": [{"time": {"label": "b", "steps": [{"hold": {"ms": 1}}]}}]}}
    assert _check(*_story([{"waitForPath": {"pattern": "(a+)+$"}}])).get("code") == "storyline_refused"
    assert _check(*_story([{"constructor": {}}])).get("code") == "storyline_refused"
    assert _check(*_story([{"time": {"label": "__proto__", "steps": [{"hold": {"ms": 1}}]}}])).get("code") == "storyline_refused"
    long_holds = [{"hold": {"ms": 30_000}}] * 30
    worst = _check({"title": "t", "ready": {"text": "x"}, "segments": [
        {"key": f"0{i}", "title": "A", "steps": long_holds} for i in range(1, 4)]},
        [{"key": f"0{i}", "title": "A"} for i in range(1, 4)])
    assert worst.get("code") == "storyline_refused" and "min" in worst["msg"], worst
    # A realistic plan with many waits on the app is never refused for its waits' timeouts.
    many_waits = [{"click": {"target": {"text": "x"}}}, {"waitVisible": {"target": {"text": "y"}}}] * 15
    assert _check({"title": "t", "ready": {"text": "x"}, "segments": [
        {"key": f"0{i}", "title": "A", "steps": many_waits} for i in range(1, 6)]},
        [{"key": f"0{i}", "title": "A"} for i in range(1, 6)])["ok"]
    assert _check(*_story([nested])).get("code") == "storyline_refused"
    assert _check(*_story([{"hold": {"ms": 1}}] * 61)).get("code") == "storyline_refused"


@needs_node
def test_the_request_policy_reads_only_and_keeps_the_app_frame_in_the_app():
    got = json.loads(_node(
        "import { demoPolicy, decide, wsAllowed } from './readonly.mjs';"
        "const crew = demoPolicy({ appOrigin: 'http://127.0.0.1:7721', launchPath: '/apps/esc', target: { kind: 'crew_app', id: 'esc' } });"
        "const plain = demoPolicy({ appOrigin: 'http://127.0.0.1:3000', launchPath: '/', target: { kind: 'loopback_app' } });"
        "const d = (p, m, u, nav = null) => decide(p, { method: m, url: u, nav }).allow;"
        "console.log(JSON.stringify({"
        " shellRead: d(crew, 'GET', 'http://127.0.0.1:7721/api/v1/health'),"
        " navOut: d(crew, 'GET', 'http://127.0.0.1:7721/api/v1/runs', 'app'),"
        " navIn: d(crew, 'GET', 'http://127.0.0.1:7721/apps/esc/x', 'app'),"
        " navPrefixTrick: d(crew, 'GET', 'http://127.0.0.1:7721/apps/escalate', 'app'),"
        " navPost: d(crew, 'POST', 'http://127.0.0.1:7721/api/v1/apps/esc/query', 'app'),"
        " stageNav: d(crew, 'GET', 'http://127.0.0.1:7721/apps/esc', 'stage'),"
        " dataDoc: d(crew, 'GET', 'data:text/html,x', 'app'),"
        " dataSub: d(crew, 'GET', 'data:image/png;base64,AA'),"
        " query: d(crew, 'POST', 'http://127.0.0.1:7721/api/v1/apps/esc/query'),"
        " otherQuery: d(crew, 'POST', 'http://127.0.0.1:7721/api/v1/apps/other/query'),"
        " gate: d(crew, 'POST', 'http://127.0.0.1:7721/api/v1/runs/r/gates/g/answer'),"
        " otherPort: d(crew, 'GET', 'http://127.0.0.1:7701/api/v1/health'),"
        " plainQuery: d(plain, 'POST', 'http://127.0.0.1:3000/api/v1/apps/esc/query'),"
        " options: d(crew, 'OPTIONS', 'http://127.0.0.1:7721/x'),"
        " ws: wsAllowed(crew, 'ws://127.0.0.1:7721/ws'), terminals: wsAllowed(crew, 'ws://127.0.0.1:7721/ws/terminals'),"
        " plainWs: wsAllowed(plain, 'ws://127.0.0.1:3000/ws') }));"
    ))
    assert got == {
        "shellRead": True, "navOut": False, "navIn": True, "navPrefixTrick": False, "navPost": False, "stageNav": False,
        "dataDoc": False, "dataSub": True, "query": True, "otherQuery": False,
        "gate": False, "otherPort": False, "plainQuery": False, "options": True, "ws": True, "terminals": False,
        "plainWs": False,
    }


@needs_node
def test_the_policy_refuses_a_non_loopback_origin():
    out = subprocess.run(
        ["node", "--input-type=module", "-e",
         "import { demoPolicy } from './readonly.mjs'; demoPolicy({ appOrigin: 'https://example.com', launchPath: '/' });"],
        cwd=DEMO, capture_output=True, text=True, timeout=60)
    assert out.returncode != 0 and "loopback" in out.stderr


# ---- end to end -----------------------------------------------------------------------------------------------


def _demo_deps_ready() -> bool:
    if shutil.which("node") is None or shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        return False
    probe = subprocess.run(
        ["node", "--input-type=module", "-e",
         "import { createRequire } from 'node:module'; import path from 'node:path'; import { DEPS_DIR } from './_playwright.mjs';"
         "createRequire(path.join(DEPS_DIR, 'package.json')).resolve('playwright');"],
        cwd=DEMO, capture_output=True, text=True, timeout=60)
    if probe.returncode != 0:
        return False
    # The browser too, not only the package: a host without Chromium skips instead of failing.
    launch = subprocess.run(
        ["node", "--input-type=module", "-e",
         "import { loadChromium } from './_playwright.mjs'; const b = await (await loadChromium()).launch(); await b.close();"],
        cwd=DEMO, capture_output=True, text=True, timeout=120)
    return launch.returncode == 0


needs_deps = pytest.mark.skipif(not _demo_deps_ready(), reason="needs node, ffmpeg/ffprobe and the demo deps (scripts/demo/setup.mjs)")


@pytest.fixture()
def app():
    sys.path.insert(0, str(FIXTURE))
    try:
        import server  # noqa: PLC0415
        srv, seen = server.start()
        yield f"http://127.0.0.1:{srv.server_address[1]}", seen
        srv.shutdown()
    finally:
        sys.path.remove(str(FIXTURE))
        sys.modules.pop("server", None)


def _run(action: str, tmp_path: Path, origin: str, steps: list | None = None, live: bool = True, jail: str | None = "test",
         launch: str = "/app", target: str = '{"kind":"loopback_app"}', story: dict | None = None, chapters: list | None = None,
         extra_env: dict | None = None, ready: dict | None = None) -> dict:
    root = tmp_path / "root"
    for d in ("demo-video", "review", "probe"):
        (root / d).mkdir(parents=True, exist_ok=True)
    snap = tmp_path / "snap"
    snap.mkdir(exist_ok=True)
    story = story or {"title": "Board demo", "ready": ready or {"role": "heading", "name": "Demo board"},
                      "segments": [{"key": "01-board", "title": "The board", "steps": steps or [{"hold": {"ms": 600}}]}]}
    chapters = chapters or [{"key": g["key"], "title": g["title"]} for g in story["segments"]]
    (snap / "storyline.json").write_text(json.dumps(story))
    (snap / "chapters.json").write_text(json.dumps(chapters))
    (tmp_path / "tmp").mkdir(exist_ok=True)
    env = {k: v for k, v in os.environ.items() if not k.startswith("WICKED_DEMO_")}
    env.update(WICKED_DEMO_ROOT=str(root), WICKED_DEMO_APP_ORIGIN=origin, WICKED_DEMO_LAUNCH_PATH=launch,
               WICKED_DEMO_TARGET=target, WICKED_DEMO_STORYLINE=str(snap),
               WICKED_DEMO_LIVE_DATA_TO_MODELS="1" if live else "0", TMPDIR=str(tmp_path / "tmp"))
    env.update(extra_env or {})
    if jail:
        env["WICKED_DEMO_JAIL"] = jail
    r = subprocess.run(["node", str(DEMO / "demo-record.mjs"), action], env=env, capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, r.stderr
    verdict = root / ("demo-video/record.json" if action == "record" else "probe/result.json")
    return json.loads(verdict.read_text())


@needs_deps
def test_a_take_records_the_floor_files_and_passes(app, tmp_path):
    origin, seen = app
    v = _run("record", tmp_path, origin, [
        {"caption": {"kicker": "Board", "title": "Everything at a glance", "readMs": 800}},
        {"click": {"target": {"button": "Open details"}}},
        {"waitVisible": {"target": {"text": "Details shown"}}},
    ])
    assert v["overall"] == "PASS", v
    root = tmp_path / "root"
    for f in ("demo-video/demo.mp4", "demo-video/chapters.md", "demo-video/timings.json", "demo-video/segments/01-board/segment.mp4",
              "review/chapters.png", "review/joins.png", "review/end.png", "review/ffprobe.json"):
        assert (root / f).is_file() and (root / f).stat().st_size > 0, f
    assert v["ffprobe"]["codec"] == "h264" and [c["title"] for c in v["ffprobe"]["chapters"]] == ["The board"]
    assert v["blocked"] == [] and v["read_only"] is True
    assert not any(s.startswith("POST") for s in seen)


@needs_deps
def test_a_click_that_routes_out_of_the_app_fails_left_app(app, tmp_path):
    origin, _ = app
    v = _run("record", tmp_path, origin, [{"click": {"target": {"button": "Leave"}}}])
    assert v["overall"] == "FAIL" and v["cause"] == "left_app", v


@needs_deps
def test_a_write_the_app_attempts_is_never_sent(app, tmp_path):
    origin, seen = app
    v = _run("record", tmp_path, origin, [{"click": {"target": {"button": "Save"}}}, {"hold": {"ms": 800}}])
    assert v["overall"] == "FAIL" and v["cause"] == "side_effect_blocked", v
    assert "POST /app/save" not in seen


@needs_deps
def test_a_redirect_out_of_the_launch_path_is_stopped_at_the_hop(app, tmp_path):
    origin, seen = app
    v = _run("record", tmp_path, origin, [{"go": {"path": "/app/jump"}}])
    assert v["overall"] == "FAIL", v
    assert "GET /app/jump" in seen and "GET /outside" not in seen, seen


@needs_deps
def test_an_app_page_that_does_not_load_fails_app_not_ready(app, tmp_path):
    origin, _ = app
    v = _run("record", tmp_path, origin, [{"go": {"path": "/app/missing"}}])
    assert v["overall"] == "FAIL" and v["cause"] == "app_not_ready", v


@needs_deps
def test_no_jail_no_recording(app, tmp_path):
    origin, seen = app
    v = _run("record", tmp_path, origin, jail=None)
    assert v["overall"] == "INCONCLUSIVE" and v["cause"] == "unjailed_host", v
    assert seen == []


@needs_deps
def test_the_probe_keeps_live_rows_out_when_told_to(app, tmp_path):
    origin, _ = app
    v = _run("probe", tmp_path, origin, live=False)
    assert v["overall"] == "PASS" and v["structure_only"] is True, v
    probe = tmp_path / "root" / "probe"
    assert not list(probe.glob("*.png"))
    text = (probe / v["page"]).read_text()
    assert "SECRET-ROW-ACME" not in text and "Demo board" in text
    v = _run("probe", tmp_path, origin, live=True)
    assert list(probe.glob("*.png")) and "SECRET-ROW-ACME" in (probe / v["page"]).read_text()


CREW = '{"kind":"crew_app","id":"esc"}'
CREW_READY = {"role": "heading", "name": "Escalations", "in": "content"}


@needs_deps
def test_a_crew_app_loads_its_rows_through_its_query_and_nothing_else(app, tmp_path):
    origin, seen = app
    v = _run("record", tmp_path, origin, [{"waitVisible": {"target": {"text": "rows saved", "in": "content"}}}, {"hold": {"ms": 400}}],
             launch="/apps/esc", target=CREW, ready=CREW_READY)
    assert v["overall"] == "PASS", v
    assert "POST /api/v1/apps/esc/query" in seen and "WS /ws" in seen, seen


@needs_deps
def test_a_terminal_socket_never_connects(app, tmp_path):
    origin, seen = app
    v = _run("record", tmp_path, origin, [{"click": {"target": {"button": "Terminal", "in": "content"}}}, {"hold": {"ms": 800}}],
             launch="/apps/esc", target=CREW, ready=CREW_READY)
    assert "WS /ws/terminals" not in seen, seen
    assert any("/ws/terminals" in u for u in v["diagnostics"]["ws_refused"]), v


@needs_deps
def test_a_web_worker_is_never_started(app, tmp_path):
    origin, seen = app
    _run("record", tmp_path, origin, [{"click": {"target": {"button": "Worker", "in": "content"}}}, {"hold": {"ms": 800}}],
         launch="/apps/esc", target=CREW, ready=CREW_READY)
    assert "GET /apps/esc/worker.js" not in seen, seen


@needs_deps
def test_a_popup_fails_the_take(app, tmp_path):
    origin, _ = app
    v = _run("record", tmp_path, origin, [{"click": {"target": {"role": "link", "name": "Pop out", "in": "content"}}}, {"hold": {"ms": 800}}],
             launch="/apps/esc", target=CREW, ready=CREW_READY)
    assert v["overall"] == "FAIL" and v["cause"] == "side_effect_blocked", v


@needs_deps
def test_a_stalled_capture_fails_capture_stalled(app, tmp_path):
    origin, _ = app
    v = _run("record", tmp_path, origin, [{"hold": {"ms": 600}}], extra_env={"WICKED_DEMO_TEST_DROP_PICTURES": "1"})
    assert v["overall"] == "INCONCLUSIVE" and v["cause"] == "capture_stalled", v


@needs_deps
def test_missing_ffmpeg_is_named_never_installed(app, tmp_path):
    origin, seen = app
    v = _run("record", tmp_path, origin, extra_env={"FFMPEG": str(tmp_path / "no-ffmpeg")})
    assert v["overall"] == "INCONCLUSIVE" and v["cause"] == "recorder_deps_missing", v
    assert any(m["tool"] == "ffmpeg" for m in v["missing"]) and "brew install ffmpeg" in v["reason"]
    assert seen == []


@needs_deps
def test_a_multichapter_take_keeps_every_chapter_in_order(app, tmp_path):
    origin, _ = app
    story = {
        "title": "Board demo", "ready": {"role": "heading", "name": "Demo board"},
        "intro": {"title": "Hello", "ms": 1500},
        "segments": [
            {"key": "01-a", "title": "Search #1; a=b", "steps": [{"time": {"label": "open", "steps": [
                {"click": {"target": {"button": "Open details"}}}, {"waitForPath": {"path": "/app/details"}}]}}]},
            {"key": "02-b", "title": "Search #1; a=b", "steps": [{"hold": {"ms": 500}}]},
        ],
        "closing": {"title": "Done", "body": "Opened in {{timings.01-a.open}}", "ms": 1500},
    }
    v = _run("record", tmp_path, origin, story=story)
    assert v["overall"] == "PASS", v
    assert [c["title"] for c in v["ffprobe"]["chapters"]] == ["Introduction", "Search #1; a=b", "Search #1; a=b"]
    starts = [c["start"] for c in v["chapters"]]
    assert starts == sorted(starts) and len(set(starts)) == 3, v["chapters"]
    assert all(c["ready_at"] is not None for c in v["chapters"][1:]), v["chapters"]
    assert (tmp_path / "root/demo-video/timings.json").read_text().count('"open"') == 1


@needs_deps
def test_a_failure_message_carries_no_page_text_when_rows_stay_out_of_models(app, tmp_path):
    origin, _ = app
    # The target resolves to a hidden element: Playwright's timeout error quotes it, page text included ("ACME").
    v = _run("record", tmp_path, origin, [{"click": {"target": {"button": "Open details"}}}, {"waitVisible": {"target": {"text": "HIDDEN-NOTE"}}}], live=False)
    assert v["overall"] == "FAIL", v
    assert "ACME" not in json.dumps(v), v
    notes = "".join(f.read_text() for f in (tmp_path / "root" / "demo-video").rglob("*.json"))
    assert "ACME" not in notes, "a failure note quotes the page"
    # The same take with rows allowed to reach a model keeps the quote (the sentinel is really in the error).
    _run("record", tmp_path / "full", origin, [{"click": {"target": {"button": "Open details"}}}, {"waitVisible": {"target": {"text": "HIDDEN-NOTE"}}}], live=True)
    full_notes = "".join(f.read_text() for f in (tmp_path / "full" / "root" / "demo-video").rglob("failure.json"))
    assert "ACME" in full_notes, "the error really quotes the page (else this test proves nothing)"


@needs_deps
def test_a_structure_only_probe_drops_link_targets_labels_and_old_outputs(app, tmp_path):
    origin, _ = app
    full = _run("probe", tmp_path, origin, launch="/apps/esc", target=CREW)
    probe = tmp_path / "root" / "probe"
    assert full["overall"] == "PASS" and list(probe.glob("*.png"))
    v = _run("probe", tmp_path, origin, live=False, launch="/apps/esc", target=CREW)
    assert v["overall"] == "PASS" and v["structure_only"] is True, v
    assert not list(probe.glob("*.png")), "the earlier full probe's screenshot must not survive"
    every = "".join(f.read_text() for f in probe.glob("*.json"))
    for secret in ("SECRET-ID-42", "SECRET-ROW-ACME", "SECRET-NOTE-7"):
        assert secret not in every, secret


@needs_node
def test_path_prefixes_match_the_root_and_a_trailing_slash():
    got = json.loads(_node(
        "import { pathPrefixRegExp } from './storyline-data.mjs';"
        "const m = (p, u) => pathPrefixRegExp(p).test(u);"
        "console.log(JSON.stringify([m('/', '/app'), m('/app/', '/app/details'), m('/app', '/app?x=1'), m('/app', '/apple')]));"
    ))
    assert got == [True, True, True, False]


@needs_node
def test_a_chapter_title_is_one_line():
    story, chapters = _story([{"hold": {"ms": 10}}])
    story["segments"][0]["title"] = "two\nlines"
    assert _check(story, chapters).get("code") == "storyline_refused"


@needs_deps
def test_a_target_inside_the_apps_own_frame_is_reachable(app, tmp_path):
    origin, _ = app
    v = _run("record", tmp_path, origin, [{"point": {"target": {"button": "Zoom", "in": "content"}, "label": "Zoom"}}, {"hold": {"ms": 300}}],
             launch="/apps/esc", target=CREW, ready={"text": "Inner chart", "in": "content"})
    assert v["overall"] == "PASS", v
    p = _run("probe", tmp_path, origin, launch="/apps/esc", target=CREW)
    summary = json.loads((tmp_path / "root" / "probe" / p["page"]).read_text())
    assert any("Inner chart" in " ".join(f["headings"]) for f in summary.get("frames", [])), summary



# ---- DES-DEMO-RECORD-001 §13 A1: a normal app records cleanly the first time ---------------------------------

@needs_node
def test_optional_is_only_for_cosmetic_steps_and_never_inside_a_measured_one():
    ok = {"click": {"target": {"button": "x"}}, "optional": True}
    assert _check(*_story([ok, {"point": {"target": {"text": "y"}, "label": "y"}, "optional": True},
                          {"waitVisible": {"target": {"text": "z"}}, "optional": False}]))["ok"]
    for bad in ({"type": {"target": {"text": "q"}, "text": "a"}, "optional": True},
                {"hold": {"ms": 10}, "optional": True},
                {"click": {"target": {"button": "x"}}, "optional": "yes"},
                {"time": {"label": "t", "steps": [ok]}}):
        got = _check(*_story([bad]))
        assert got.get("code") == "storyline_refused" and got["where"].endswith(".optional"), (bad, got)


@needs_node
def test_a_crew_app_storyline_targets_only_the_apps_own_frame():
    story, chapters = _story([{"click": {"target": {"button": "x", "in": "content"}}}])
    story["ready"]["in"] = "content"
    assert _check(story, chapters, content_only=True)["ok"]
    story["ready"].pop("in")
    got = _check(story, chapters, content_only=True)
    assert got.get("code") == "storyline_refused" and got["where"] == "storyline.ready.in", got
    story["ready"]["in"] = "content"
    story["segments"][0]["steps"] = [{"point": {"target": {"text": "outer"}, "label": "l"}}]
    assert _check(story, chapters, content_only=True)["where"] == "storyline.segments[0].steps[0].point.target.in"
    assert _check(story, chapters)["ok"], "a loopback app's page is the app: any target is fine"


@needs_node
def test_hide_takes_one_selector_per_entry_and_nothing_that_ends_a_rule():
    story, chapters = _story([{"hold": {"ms": 10}}])
    story["hide"] = [{"css": "#banner, .toast[data-x='1']"}, {"css": "header", "in": "content"}]
    assert _check(story, chapters)["ok"]
    for css in ("x{}", "a;b", "@import url(x)", "a/*b*/", "a\\{", "<b>", " "):
        story["hide"] = [{"css": css}]
        got = _check(story, chapters)
        assert got.get("code") == "storyline_refused" and got["where"].startswith("storyline.hide[0]"), (css, got)
    story["hide"] = [{"css": "a"}] * 13
    assert _check(story, chapters).get("code") == "storyline_refused"


@needs_node
def test_a_chapters_first_target_stops_at_anything_that_changes_the_page():
    got = json.loads(_node(
        "import { firstTarget } from './storyline-data.mjs';"
        "const t = (v, o) => ({ verb: 'waitVisible', target: { kind: 'text', value: v }, ...(o ? { optional: true } : {}) });"
        "console.log(JSON.stringify([firstTarget([{ verb: 'caption' }, t('a')])?.value ?? null,"
        " firstTarget([t('skip', true), t('b')])?.value ?? null, firstTarget([{ verb: 'go', path: '/x' }, t('c')]),"
        " firstTarget([{ verb: 'time', steps: [t('d')] }])]));"
    ))
    assert got == ["a", "b", None, None]


@needs_node
def test_a_cut_keeps_one_frame_of_its_span_and_moves_what_follows_earlier():
    got = json.loads(_node(
        "import { videoClock } from './postprocess.mjs';"
        "const tl = { t0: 0, capture: { fps: 30 }, marks: { speed: [{ start: 2, end: 8, factor: 1, cut: true }] } };"
        "const c = videoClock(tl, 0);"
        "console.log(JSON.stringify([c.outAt(1), Math.round(c.outAt(10) * 30), c.spans.length]));"
    ))
    # 10 s of master: 2 s before the cut, one kept frame of its 6 s, then 2 s after it.
    assert got == [1, 2 * 30 + 1 + 2 * 30, 1], got


def _red_share(video: Path, at: float, tmp: Path) -> float:
    """The share of a frame's pixels that are the fixture's chrome red (a small decode of the frame at `at`)."""
    ffmpeg = os.environ.get("FFMPEG", "ffmpeg")
    r = subprocess.run([ffmpeg, "-v", "error", "-ss", str(at), "-i", str(video), "-frames:v", "1", "-vf", "scale=192:108",
                        "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True, timeout=60)
    assert r.returncode == 0 and len(r.stdout) == 192 * 108 * 3, r.stderr
    px = r.stdout
    red = sum(1 for i in range(0, len(px), 3) if px[i] > 190 and px[i + 1] < 70 and px[i + 2] < 70)
    return red / (192 * 108)


def _ready_at(v: dict) -> float:
    return next(c for c in v["chapters"] if c["key"] != "intro")["ready_at"]


@needs_deps
def test_a_crew_app_take_shows_its_own_frame_and_never_studios_chrome(app, tmp_path):
    origin, _ = app
    steps = [{"waitVisible": {"target": {"text": "rows saved", "in": "content"}}}, {"hold": {"ms": 600}}]
    v = _run("record", tmp_path, origin, steps, launch="/apps/esc", target=CREW, ready=CREW_READY)
    assert v["overall"] == "PASS" and v["view"] == "app_frame", v
    video = tmp_path / "root" / "demo-video" / "demo.mp4"
    # (test_a_hide_entry_keeps_a_dev_banner_out_of_frame proves the same red is seen when it is in the picture.)
    for at in (_ready_at(v) + 0.3, v["chapters"][0]["end"] - 1.5):
        assert _red_share(video, at, tmp_path) < 0.002, f"studio's banner or chat is in the picture at {at}"


@needs_deps
def test_a_hide_entry_keeps_a_dev_banner_out_of_frame(app, tmp_path):
    origin, _ = app
    story = {"title": "Board demo", "ready": {"role": "heading", "name": "Demo board"}, "hide": [{"css": "#devbar"}, {"css": "a:::b"}],
             "segments": [{"key": "01-board", "title": "The board", "steps": [{"hold": {"ms": 600}}]}]}
    v = _run("record", tmp_path, origin, story=story)
    assert v["overall"] == "PASS" and v["hide_invalid"] == ["a:::b"], v
    assert _red_share(tmp_path / "root" / "demo-video" / "demo.mp4", _ready_at(v) + 0.3, tmp_path) < 0.002
    story.pop("hide")
    shown = _run("record", tmp_path / "shown", origin, story=story)
    assert _red_share(tmp_path / "shown" / "root" / "demo-video" / "demo.mp4", _ready_at(shown) + 0.3, tmp_path) > 0.02


@needs_deps
def test_a_slow_app_gets_ready_behind_the_card_and_the_wait_is_cut(app, tmp_path):
    origin, _ = app
    sys.modules["server"].Handler.query_delay = 7.0
    steps = [{"waitVisible": {"target": {"text": "rows saved", "in": "content"}}}, {"hold": {"ms": 500}}]
    v = _run("record", tmp_path, origin, steps, launch="/apps/esc", target=CREW, ready=CREW_READY)
    assert v["overall"] == "PASS", v
    ch = v["chapters"][0]
    # About 7 s of loading, of which all but the card's own 3 s is cut; the app is on screen, ready, about 4-5 s in.
    assert ch["load_cut_s"] >= 3, ch
    assert ch["ready_at"] - ch["start"] < 7.5, ch
    # The rows were there when the card lifted: the chapter's wait for them took no time on screen.
    assert ch["end"] - ch["ready_at"] < 4.5, ch


@needs_deps
def test_an_optional_step_that_misses_is_skipped_and_said(app, tmp_path):
    origin, _ = app
    v = _run("record", tmp_path, origin, [{"click": {"target": {"role": "button", "name": "✕"}}, "optional": True},
                                          {"click": {"target": {"button": "Open details"}}}, {"waitVisible": {"target": {"text": "Details shown"}}}])
    assert v["overall"] == "PASS", v
    sk = v["chapters"][0]["skipped_steps"]
    assert [x["step"] for x in sk] == ["storyline.segments[0].steps[0]"] and sk[0]["verb"] == "click", sk


@needs_deps
def test_a_required_step_that_fails_names_the_step_even_when_redacted(app, tmp_path):
    origin, _ = app
    v = _run("record", tmp_path, origin, [{"click": {"target": {"button": "Open details"}}}, {"waitVisible": {"target": {"text": "Never there"}}}],
             live=False)
    assert v["overall"] == "FAIL" and v["cause"] == "step_failed", v
    assert 'storyline.segments[0].steps[1] (waitVisible text "Never there")' in v["reason"], v
