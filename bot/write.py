"""Run Claude Code (headless) to write or revise run/draft.json, then the code checks.
If the checks block, Claude gets one automatic fix round with the exact problems.

    python bot/write.py <slot> [--feedback "reviewer's request"]
Needs the `claude` CLI (npm i -g @anthropic-ai/claude-code) and CLAUDE_CODE_OAUTH_TOKEN.
Exit 0 = draft passes the checks, 1 = still blocked (the reviewer sees the problems).
"""
import json, os, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
RUN = Path(os.environ.get("STICKBIZ_RUN", ROOT / "run"))
PROMPT = (ROOT / "prompts" / "write_script.md").read_text(encoding="utf-8")


def claude(task):
    cmd = ["claude", "-p", task, "--allowedTools", "Read,Write,Edit,Glob,Grep", "--permission-mode", "acceptEdits",
           "--max-turns", "40", "--output-format", "text"]
    model = os.environ.get("CLAUDE_MODEL", "").strip()
    if model:
        cmd += ["--model", model]
    print("claude: writing…", flush=True)
    r = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, encoding="utf-8", timeout=1500, shell=(os.name == "nt"))
    print((r.stdout or "")[-1500:], (r.stderr or "")[-800:], flush=True)
    if r.returncode != 0:
        raise SystemExit(f"claude exited with {r.returncode}")


def run_checks():
    r = subprocess.run([sys.executable, str(ROOT / "bot" / "checks.py")], cwd=ROOT, text=True, capture_output=True, encoding="utf-8")
    print(r.stdout[-3000:], flush=True)
    return r.returncode == 0


def main():
    slot = sys.argv[1]
    feedback = sys.argv[sys.argv.index("--feedback") + 1] if "--feedback" in sys.argv else ""
    fb = RUN / "feedback.md"
    if feedback:
        fb.write_text(f"# Reviewer's request\n\n{feedback}\n\n# Current draft\n\n```json\n"
                      + (RUN / "draft.json").read_text(encoding="utf-8") + "\n```\n", encoding="utf-8")
        claude(PROMPT + "\n\n---\nA reviewer asked for changes: read run/feedback.md and revise run/draft.json.")
    else:
        fb.unlink(missing_ok=True)
        claude(PROMPT + f"\n\n---\nToday's slot: {slot}. Write run/draft.json now.")
    json.loads((RUN / "draft.json").read_text(encoding="utf-8"))   # must be valid JSON
    if run_checks():
        return 0
    problems = json.loads((RUN / "checks.json").read_text(encoding="utf-8"))["blocking"]
    fb.write_text("# Automatic checks failed — fix ONLY these problems, keep everything else\n\n"
                  + "\n".join(f"- {p}" for p in problems) + "\n\n# Current draft\n\n```json\n"
                  + (RUN / "draft.json").read_text(encoding="utf-8") + "\n```\n", encoding="utf-8")
    claude(PROMPT + "\n\n---\nThe automatic checks blocked the draft: read run/feedback.md and fix run/draft.json.")
    ok = run_checks()
    fb.unlink(missing_ok=True)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
