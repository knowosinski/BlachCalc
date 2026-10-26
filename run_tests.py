"""Uruchamia wszystkie testy BlachCalc z małym okienkiem postępu.

python run_tests.py              okienko z licznikiem "wykonano X z N"
python run_tests.py --no-gui     tryb tekstowy (np. na serwerze CI)
"""
import argparse
import json
import os
import queue
import subprocess
import sys
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MARKER = "@@"


def _emit(event: dict) -> None:
    sys.__stdout__.write(MARKER + json.dumps(event, ensure_ascii=False) + "\n")
    sys.__stdout__.flush()


class ProgressResult(unittest.TestResult):
    def __init__(self, total: int) -> None:
        super().__init__()
        self.total = total
        self.done = 0

    def startTest(self, test: unittest.TestCase) -> None:
        super().startTest(test)
        _emit({"event": "start", "test": test.id()})

    def stopTest(self, test: unittest.TestCase) -> None:
        super().stopTest(test)
        self.done += 1
        _emit({"event": "progress", "done": self.done, "total": self.total})

    def _problem(self, kind: str, test: unittest.TestCase, error: tuple) -> None:
        _emit({
            "event": "problem",
            "kind": kind,
            "test": test.id(),
            "details": self._exc_info_to_string(error, test),
        })

    def addFailure(self, test, err) -> None:
        super().addFailure(test, err)
        self._problem("FAIL", test, err)

    def addError(self, test, err) -> None:
        super().addError(test, err)
        self._problem("ERROR", test, err)

    def addSkip(self, test, reason) -> None:
        super().addSkip(test, reason)
        _emit({"event": "skip", "test": test.id(), "reason": reason})


def run_worker() -> int:
    sys.path.insert(0, str(ROOT))
    os.chdir(ROOT)
    suite = unittest.defaultTestLoader.discover(str(ROOT), pattern="test_*.py")
    total = suite.countTestCases()
    _emit({"event": "total", "total": total})
    sys.stdout = sys.stderr = open(os.devnull, "w", encoding="utf-8")
    result = ProgressResult(total)
    suite.run(result)
    try:
        import ui_harness

        ui_harness.shutdown()
    except ImportError:
        pass
    ok = result.wasSuccessful()
    _emit({
        "event": "done",
        "ok": ok,
        "run": result.testsRun,
        "failures": len(result.failures),
        "errors": len(result.errors),
        "skipped": len(result.skipped),
    })
    return 0 if ok else 1


def start_worker() -> subprocess.Popen:
    environment = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"}
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return subprocess.Popen(
        [sys.executable, str(Path(__file__).resolve()), "--worker"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=ROOT,
        env=environment,
        creationflags=flags,
    )


def read_events(process: subprocess.Popen, events: "queue.Queue[dict | None]") -> None:
    assert process.stdout is not None
    for line in process.stdout:
        line = line.rstrip("\n")
        if line.startswith(MARKER):
            try:
                events.put(json.loads(line[len(MARKER):]))
            except json.JSONDecodeError:
                events.put({"event": "log", "line": line})
        elif line:
            events.put({"event": "log", "line": line})
    events.put(None)


def run_text() -> int:
    process = start_worker()
    events: "queue.Queue[dict | None]" = queue.Queue()
    threading.Thread(target=read_events, args=(process, events), daemon=True).start()
    problems: list[dict] = []
    log: list[str] = []
    summary: dict = {}
    while (event := events.get()) is not None:
        if event["event"] == "progress":
            print(f"\rWykonano {event['done']} z {event['total']} testów", end="", flush=True)
        elif event["event"] == "problem":
            problems.append(event)
        elif event["event"] == "done":
            summary = event
        elif event["event"] == "log":
            log.append(event["line"])
    print()
    for problem in problems:
        print(f"\n{problem['kind']}: {problem['test']}\n{problem['details']}")
    if not summary:
        print("Proces testów zakończył się nieoczekiwanie:\n" + "\n".join(log[-20:]))
        return 1
    print(
        f"Testy: {summary['run']}, błędy: {summary['failures'] + summary['errors']}, "
        f"pominięte: {summary['skipped']}"
    )
    return 0 if summary["ok"] else 1


def run_gui() -> int:
    import tkinter as tk
    from tkinter import ttk

    root = tk.Tk()
    root.title("BlachCalc — testy")
    root.resizable(False, False)
    root.attributes("-topmost", True)
    frame = ttk.Frame(root, padding=16)
    frame.pack(fill="both", expand=True)

    counter = tk.StringVar(value="Przygotowanie testów…")
    current = tk.StringVar(value="")
    ttk.Label(frame, textvariable=counter, font=("Segoe UI", 12, "bold")).pack(anchor="w")
    bar = ttk.Progressbar(frame, length=420, mode="indeterminate")
    bar.pack(fill="x", pady=(10, 6))
    bar.start(12)
    ttk.Label(frame, textvariable=current, foreground="#64748B", wraplength=420).pack(anchor="w")
    details = tk.Text(frame, height=12, width=70, wrap="word", state="disabled")
    close_button = ttk.Button(frame, text="Zamknij", command=root.destroy)

    process = start_worker()
    events: "queue.Queue[dict | None]" = queue.Queue()
    threading.Thread(target=read_events, args=(process, events), daemon=True).start()
    state = {"total": 0, "done": 0, "problems": [], "log": [], "summary": None, "exit": 1}

    def center() -> None:
        root.update_idletasks()
        x = (root.winfo_screenwidth() - root.winfo_width()) // 2
        y = (root.winfo_screenheight() - root.winfo_height()) // 3
        root.geometry(f"+{x}+{y}")

    def show_problems(text: str) -> None:
        details.configure(state="normal")
        details.insert("1.0", text)
        details.configure(state="disabled")
        details.pack(fill="both", expand=True, pady=(10, 0))
        close_button.pack(anchor="e", pady=(10, 0))
        center()

    def finish() -> None:
        bar.stop()
        summary = state["summary"]
        if summary is None:
            bar.configure(mode="determinate", value=0)
            counter.set("Testy przerwane — proces zakończył się nieoczekiwanie")
            show_problems("\n".join(state["log"][-30:]) or "Brak informacji z procesu testów.")
            return
        bar.configure(mode="determinate", maximum=max(state["total"], 1), value=state["done"])
        errors = summary["failures"] + summary["errors"]
        if summary["ok"] and state["done"] >= state["total"]:
            state["exit"] = 0
            counter.set(f"Wszystkie testy zakończone pomyślnie: {summary['run']} z {state['total']}")
            current.set(f"Pominięte: {summary['skipped']}")
            root.after(1500, root.destroy)
            return
        counter.set(f"Błędy w testach: {errors} (wykonano {state['done']} z {state['total']})")
        show_problems("\n\n".join(
            f"{p['kind']}: {p['test']}\n{p['details']}" for p in state["problems"]
        ) or "Nie wszystkie testy zostały uruchomione.")

    def poll() -> None:
        finished = False
        for _ in range(200):
            try:
                event = events.get_nowait()
            except queue.Empty:
                break
            if event is None:
                finished = True
                break
            kind = event["event"]
            if kind == "total":
                state["total"] = event["total"]
                bar.stop()
                bar.configure(mode="determinate", maximum=max(event["total"], 1), value=0)
                counter.set(f"Wykonano 0 z {event['total']} testów")
            elif kind == "start":
                current.set(event["test"].rsplit(".", 2)[-2] + " · " + event["test"].rsplit(".", 1)[-1])
            elif kind == "progress":
                state["done"] = event["done"]
                bar.configure(value=event["done"])
                counter.set(f"Wykonano {event['done']} z {event['total']} testów")
            elif kind == "problem":
                state["problems"].append(event)
            elif kind == "done":
                state["summary"] = event
            elif kind == "log":
                state["log"].append(event["line"])
        if finished:
            finish()
        else:
            root.after(40, poll)

    center()
    root.after(40, poll)
    root.mainloop()
    if process.poll() is None:
        process.kill()
    return state["exit"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--no-gui", action="store_true", help="tryb tekstowy bez okienka")
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    arguments = parser.parse_args()
    if arguments.worker:
        return run_worker()
    return run_text() if arguments.no_gui else run_gui()


if __name__ == "__main__":
    sys.exit(main())
