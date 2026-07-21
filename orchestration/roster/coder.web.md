<!-- roster entry — binds a role to a spec + addressing. Architect-owned. CR052. -->
# coder.web

```
role: coder
spec: website + website_api (marketing island)
kind: code
owns: website/** (static HTML/CSS/assets, deploy_ftp.py), website_api/** (own FastAPI app, own DB
       ami_website, own tests)
wip_cap: 2
auditor: auditor.core
live_handle:
commit_tag: AT:coder.web
worktree: .claude/worktrees/coder.web-<ITEM>
active_lanes: []
```

**Fully independent island** — zero shared code with `backend/` or `mobile/` (own package, own DB,
own FTP/Docker deploy). Near-zero collision risk with any other instance. Test command: the
`website_api/` pytest suite for API changes; static preview for `website/`.
