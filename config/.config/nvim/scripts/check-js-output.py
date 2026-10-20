#!/usr/bin/env python3
"""Exercise JS diagnostics and task-terminal keyboard behavior in an attached UI.

Requires pynvim (can run in a temporary virtualenv). Uses temporary examples only.
"""
import json
import faulthandler
import tempfile
import time
from pathlib import Path

import pynvim


root = Path(tempfile.mkdtemp(prefix="nvim-js-output-"))
results = []
nvim = pynvim.attach("child", argv=["nvim", "--embed", "-n", "-i", "NONE"])
faulthandler.dump_traceback_later(30, repeat=True)


def wait_for(predicate, message, timeout=12):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.04)
    raise AssertionError(message)


def check(name, callback):
    try:
        callback()
        results.append({"name": name, "passed": True})
        print("PASS", name, flush=True)
    except Exception as error:
        results.append({"name": name, "passed": False, "error": str(error)})
        print("FAIL", name, str(error), flush=True)
        raise


def mode():
    return nvim.api.get_mode()["mode"]


def lines(buf):
    return nvim.api.buf_get_lines(buf, 0, -1, False)


def done(buf):
    return nvim.exec_lua("return vim.b[...].workbench_exit_code", buf) is not None


def edit(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    nvim.command("edit " + nvim.funcs.fnameescape(str(path)))
    return nvim.current.buffer.number


def diagnostics(buf):
    return nvim.exec_lua("return vim.diagnostic.get(..., {severity = 1})", buf)


def run_file():
    nvim.input(" rf")
    wait_for(lambda: nvim.current.buffer.options["buftype"] == "terminal", "rf did not open output")
    return nvim.current.buffer.number


def task(code, title):
    return nvim.exec_lua(
        "local code, root, title = ...; "
        "return require('workbench.tasks').terminal({'/usr/bin/node', '-e', code}, root, title)",
        code, str(root), title,
    )


def js_diagnostics():
    buf = edit(root / "standalone" / "hola.js",
               'console.log("Hola mundo");\n\nconsole.log(2 + 2);\ncnsole.log(2 + 1213);\n')
    wait_for(lambda: any(d["lnum"] == 3 and "cnsole" in d["message"] for d in diagnostics(buf)),
             "Standalone JS typo was not reported", timeout=35)
    assert all(d["lnum"] == 3 for d in diagnostics(buf)), diagnostics(buf)
    nvim.api.buf_set_lines(buf, 3, 4, False, ['console.log(2 + 1213);'])
    wait_for(lambda: not diagnostics(buf), "Correct console.log still has errors")
    nvim.current.buffer.options["modified"] = False


def js_opt_out():
    project = root / "explicit-project"
    project.mkdir()
    (project / "jsconfig.json").write_text('{"compilerOptions":{"checkJs":false}}')
    for path, text in [
        (project / "unchecked.js", "cnsole.log(1);\n"),
        (root / "standalone" / "nocheck.js", "// @ts-nocheck\ncnsole.log(1);\n"),
    ]:
        buf = edit(path, text)
        wait_for(lambda: nvim.exec_lua("return vim.b[...].check_diagnostics_seen == true", buf),
                 "No diagnostic update for opt-out", timeout=35)
        assert not diagnostics(buf), diagnostics(buf)


def error_output():
    source = edit(root / "runtime" / "error.js",
                  'console.log("Hola mundo");\nconsole.log(2 + 2);\ncnsole.log(2 + 1213);\n')
    print("  run error.js", flush=True)
    buf = run_file()
    wait_for(lambda: done(buf) and mode() == "nt", "Finished output did not enter Terminal-normal")
    assert any("ReferenceError: cnsole is not defined" in line for line in lines(buf))
    status = nvim.api.eval_statusline(nvim.eval("&statusline"), {})["str"]
    assert "Node" in status and "salida 1" in status and "gg inicio" in status, status
    nvim.input("gg")
    wait_for(lambda: nvim.current.window.cursor[0] == 1, "Could not reach start of error output")
    print("  finished normally; testing navigation", flush=True)
    nvim.input("<Down>")
    wait_for(lambda: nvim.current.window.cursor[0] == 2, "Arrow key did not navigate")
    assert nvim.current.buffer.number == buf
    nvim.input("/ReferenceError<CR>")
    wait_for(lambda: "ReferenceError" in nvim.current.line, "Keyboard search failed")
    nvim.input("i")
    wait_for(lambda: mode() == "nt", "i reactivated a dead terminal")
    print("  dead terminal refuses input mode", flush=True)
    nvim.input("gg")
    wait_for(lambda: nvim.current.window.cursor[0] == 1, "gg did not move to start")
    assert nvim.api.buf_is_valid(buf), "A key discarded output"
    nvim.input("q")
    wait_for(lambda: nvim.current.buffer.number == source, "q did not return to source")
    assert nvim.api.buf_is_loaded(buf), "q discarded output instead of hiding the panel"
    nvim.command("sbuffer " + str(buf))
    print("  reopened output", flush=True)
    nvim.input("i")
    wait_for(lambda: mode() == "nt", "Reopened completed terminal accepted input")
    assert nvim.current.buffer.number == buf and nvim.api.buf_is_loaded(buf)
    nvim.input("gg")
    wait_for(lambda: nvim.current.window.cursor[0] == 1, "Reopened output is not navigable")
    nvim.input("<Down>")
    wait_for(lambda: nvim.current.window.cursor[0] == 2, "Reopened output disappeared")
    nvim.input("q")
    wait_for(lambda: nvim.current.buffer.number == source, "Reopened output would not close")


def scroll_output():
    source = edit(root / "runtime" / "long.js",
                  'for (let i = 1; i <= 100; i++) console.log("línea", i);\n')
    buf = run_file()
    wait_for(lambda: done(buf) and mode() == "nt", "Successful output remained in input mode")
    nvim.input("gg")
    wait_for(lambda: nvim.current.window.cursor[0] == 1, "gg failed")
    nvim.input("<C-d>")
    wait_for(lambda: nvim.current.window.cursor[0] > 1, "Ctrl+D did not scroll")
    nvim.input("G")
    wait_for(lambda: nvim.current.window.cursor[0] == len(lines(buf)), "G failed")
    end = nvim.current.window.cursor[0]
    nvim.input("<C-u>")
    wait_for(lambda: nvim.current.window.cursor[0] < end, "Ctrl+U did not scroll")
    nvim.input("<C-w>k")
    wait_for(lambda: nvim.current.buffer.number == source, "Ctrl+W k did not return to code")
    nvim.command("wincmd j")
    nvim.input("q")
    wait_for(lambda: nvim.current.buffer.number == source, "q failed")


def interactive_focus():
    first = task('process.stdin.once("data", () => {console.log("finished"); process.exit(0)});', "Background")
    wait_for(lambda: mode() == "t", "Running task did not accept input")
    first_job = nvim.exec_lua("return vim.b[...].terminal_job_id", first)
    nvim.input("<Esc>")
    wait_for(lambda: mode() == "nt", "Esc did not leave task input mode")
    second = task('process.stdin.on("data", data => {console.log("echo:" + data.toString().trim()); '
                  'if (data.toString().trim() === "quit") process.exit(0)});', "Interactive")
    wait_for(lambda: mode() == "t", "Second task did not accept input")
    nvim.funcs.chansend(first_job, "finish\n")
    wait_for(lambda: done(first), "Background task did not finish")
    assert nvim.current.buffer.number == second and mode() == "t", "Background exit stole focus/input"
    nvim.input("hello<CR>")
    wait_for(lambda: any("echo:hello" in line for line in lines(second)), "Interactive stdin broken")
    nvim.input("<C-x>")
    wait_for(lambda: mode() == "nt", "Existing Ctrl+X mapping broken")
    nvim.input("i")
    wait_for(lambda: mode() == "t", "Could not resume a running task")
    nvim.input("quit<CR>")
    wait_for(lambda: done(second) and mode() == "nt", "Interactive exit did not become readable")


try:
    nvim.ui_attach(120, 42, rgb=True)
    nvim.exec_lua("vim.opt.undofile = false; require('persistence').stop(); "
                  "vim.api.nvim_create_autocmd('DiagnosticChanged', {callback = function(args) "
                  "vim.b[args.buf].check_diagnostics_seen = true end})")
    nvim.command("cd " + nvim.funcs.fnameescape(str(root)))
    check("Plain JS detects cnsole and clears after correction", js_diagnostics)
    check("Explicit project and file opt-outs are respected", js_opt_out)
    check("Error output survives keys, search and reopening", error_output)
    check("gg/G, Ctrl+U/D and window navigation", scroll_output)
    check("Interactive input and background completion preserve focus", interactive_focus)
finally:
    faulthandler.cancel_dump_traceback_later()
    (root / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2))
    print("Resultados:", root, flush=True)
    try:
        nvim.command("qa!")
    except (EOFError, OSError):
        pass

if not results or not all(result["passed"] for result in results):
    raise SystemExit(1)
