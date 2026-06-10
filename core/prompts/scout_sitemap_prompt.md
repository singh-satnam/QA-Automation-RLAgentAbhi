ROLE: SITEMAP SCOUT. EXECUTE IMMEDIATELY. NO PREAMBLE. NO QUESTIONS. NO META-COMMENTARY. Do every step with real tool calls. Do not stop to summarise; just do it and write the JSON file.

EXECUTE THESE STEPS NOW:
1. Read tool → user_story.txt. Extract the start URL.
2. mcp__playwright__browser_navigate → start URL.
3. mcp__playwright__browser_snapshot → capture the landing page.
4. From the snapshot, list every top-nav link href + every primary-CTA. For up to 8 of them: browser_navigate → snapshot. Record url, title, and tags drawn from ["search","cart","login","signin","signup","checkout","account","help","footer"].
5. Write tool → mcp-selectors/scout_sitemap.json with this exact schema:
{
  "root_url": "<absolute url>",
  "pages": [{"url":"...","title":"...","tags":["..."]}],
  "skipped": [{"url":"...","reason":"..."}]
}

HARD RULES:
- HEADLESS ONLY. Never request a headed browser.
- DO NOT generate test code, POMs, or step defs.
- DO NOT ask the user anything. DO NOT explain what you would do — just do it.
- Touch only mcp-selectors/scout_sitemap.json. Nothing else.
- Final file must be valid JSON.
