#!/usr/bin/env python3
import re, subprocess, os, sys, tempfile
import anthropic
from pathlib import Path
from dotenv import load_dotenv
if not os.environ.get("ANTHROPIC_API_KEY"):
    print(Path.cwd())
    sys.exit("Error: set ANTHROPIC_API_KEY in your environment.")
load_dotenv()   # call before anthropic.Anthropic()

SYSTEM = ("You are a C compiler backend. Translate the given preprocessed C into "
          "x86-64 GNU assembly (AT&T syntax, System V ABI). Output ONLY assembly, "
          "no prose, no markdown fences.")

def real_gcc(src, out):
    subprocess.run(["gcc", src, "-o", out], check=True)

def main():
    src, out = sys.argv[1], sys.argv[2]
    pre = subprocess.run(["gcc", "-E", "-P", src],
                         capture_output=True, text=True, check=True).stdout
    client = anthropic.Anthropic()          # reads ANTHROPIC_API_KEY
    messages = [{"role": "user", "content": pre}]

    for attempt in range(3):
        resp = client.messages.create(model="claude-sonnet-5-5",
                                      max_tokens=8000,
                                      system=SYSTEM, messages=messages)
        asm = resp.content[0].text.strip()
        asm = re.sub(r"^```\w*\n|\n?```$", "", asm)   # strip fences if present

        with tempfile.NamedTemporaryFile("w", suffix=".s", delete=False) as f:
            f.write(asm + "\n")
        r = subprocess.run(["gcc", f.name, "-o", out],
                           capture_output=True, text=True)
        if r.returncode == 0:
            return
        # feed the assembler/linker error back to the model
        messages += [{"role": "assistant", "content": asm},
                     {"role": "user", "content": f"Assembler error:\n{r.stderr}\nFix it."}]

    print("AI backend failed, falling back to real gcc", file=sys.stderr)
    real_gcc(src, out)

main()