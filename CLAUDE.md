# CLAUDE.md - Standing Rules for AutoMates Backend (trend-collector-service)

## Working scope
- ALL work happens inside the trend-collector/ folder ONLY.
- Everything outside trend-collector/ is legacy. Treat it as READ-ONLY. Never modify, move, or delete anything outside trend-collector/ without Kevin's explicit approval in that session.

## Hard rules - no exceptions
1. NEVER delete any file. If a file seems obsolete, flag it and ask.
2. Build ONLY what the current session's spec/prompt defines. No improvising, no scope additions, no "while I'm here" changes.
3. One task at a time. For any change touching multiple files, present the plan and the list of affected files FIRST and wait for approval before editing.
4. After EVERY edit to a Python file, run: python -c "import ast; ast.parse(open('FILENAME').read()); print('SYNTAX OK')" and show the result.
5. Never deploy, never change anything related to DNS, Render, or Cloudflare. Commits are fine when asked. Push ONLY when Kevin explicitly asks in that session — never push on your own initiative.
6. Never read, print, or modify .env files or any secrets/credentials.
7. If the spec conflicts with the code's reality, or two instructions conflict, STOP and ask. Do not resolve conflicts silently.
8. Own mistakes immediately and plainly, then fix them.

## Context
- This is the backend for AutoMates (HomeBridge Group, LLC), serving SSR agent authority pages and the content platform. app.py is large - use grep to locate, view only relevant ranges, edit with precise anchors.
- Kevin is non-developer-adjacent: explain what you're doing in plain English, one step at a time.
