# CLAUDE.md - Standing Rules for AutoMates Backend (trend-collector-service)

## Working scope
- ALL work happens inside the trend-collector/ folder ONLY.
- Everything outside trend-collector/ is legacy. Treat it as READ-ONLY. Never modify, move, or delete anything outside trend-collector/ without Kevin's explicit approval in that session.

## Hard rules - no exceptions
1. NEVER delete any file. If a file seems obsolete, flag it and ask.
2. Build ONLY what the current session's spec/prompt defines. No improvising, no scope additions, no "while I'm here" changes.
3. One task at a time. For any change touching multiple files, present the plan and the list of affected files FIRST and wait for approval before editing.
4. After EVERY edit to a Python file, run: python -c "import ast; ast.parse(open('FILE', encoding='utf-8').read()); print('SYNTAX OK')" and show the result. The explicit encoding='utf-8' is required — on this Windows machine the bare open() defaults to cp1252 and fails on UTF-8 files (e.g. em dashes in app.py), which looks like a syntax error but is not.
5. git commit, git push, and deploy happen ONLY when Kevin gives a direct instruction in that session. NEVER on your own initiative, and never because repo history suggests a pattern. You may edit and stage files; publishing waits for Kevin's explicit word. Never change anything related to DNS, Render, or Cloudflare.
6. Never read, print, or modify .env files or any secrets/credentials.
7. If the spec conflicts with the code's reality, or two instructions conflict, STOP and ask. Do not resolve conflicts silently.
8. Own mistakes immediately and plainly, then fix them.
9. Commit messages: never add a Co-Authored-By trailer or any AI-attribution line to any commit message, in any repo. There are security and crawler reasons this must not appear.
10. Editing large or multi-line blocks: the interactive edit tool can mis-fit multi-line block replacements (it has spliced new code into the middle of old code and silently mangled blocks on this Windows setup). For any multi-line block replacement, use a Python binary read/write script that asserts exactly one match for each anchor before writing, and writes nothing if any anchor does not match exactly once. Verify after writing by reading the changed region back from disk.
11. Non-ASCII / escape characters: the terminal can mis-render characters (a forward slash shown as a backslash; an escape like \u203a shown as its glyph). When any separator or special character looks wrong, or when writing a non-ASCII/escape character, verify at the byte level with Python repr() and isascii() rather than trusting the diff preview. Build backslashes in shell-bound scripts via chr(92) to avoid heredoc corruption.
12. No em dashes anywhere - in code, comments, content, commit messages, or legal text. Use hyphens. (Reaffirming the existing rule for visibility.)

## Context
- This is the backend for AutoMates (HomeBridge Group, LLC), serving SSR agent authority pages and the content platform. app.py is large - use grep to locate, view only relevant ranges, edit with precise anchors.
- Kevin is non-developer-adjacent: explain what you're doing in plain English, one step at a time.
