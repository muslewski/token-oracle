# Changelog

All notable changes to token-oracle are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.2](https://github.com/muslewski/token-oracle/compare/token-oracle-v0.1.1...token-oracle-v0.1.2) (2026-07-20)


### Features

* **adapters:** shared segment body + adaptive statusline/tmux HUD ([b0318a6](https://github.com/muslewski/token-oracle/commit/b0318a67dc603b190296f118fd0c1c89daf80f7d))
* **cli:** dash-quality surfaces — palette, forecast hero, doctor, report ([42461d7](https://github.com/muslewski/token-oracle/commit/42461d7be3b783daf0e62403e1da1a94a9f254f0))
* **cli:** implement 'oracle live on/off/status' + honor config in live-probe ([890e650](https://github.com/muslewski/token-oracle/commit/890e650db35f998f1e43b11f38757f1aaae580db))
* **cli:** init and clean subcommands (config bootstrap + user-data removal) ([9e28bd5](https://github.com/muslewski/token-oracle/commit/9e28bd5bd6efdee14b67dd3340ca8e74eb1df629))
* **cli:** interactive init wizard + project config discovery (021) ([e076122](https://github.com/muslewski/token-oracle/commit/e0761229759ec03bc7a62d2c1b71b55aa1731821))
* **cli:** opt-in snapshot write-through from forecast/statusline/tmux ([9a0173f](https://github.com/muslewski/token-oracle/commit/9a0173f9aab942591ac857daa180ad40357895f9))
* **cli:** oracle report — daily cost+cap ledger (subcommand + dispatch) ([061026f](https://github.com/muslewski/token-oracle/commit/061026f5f33c24d743657d1930418c32f67f1ad5))
* **cli:** register 'oracle live on|off|status' subcommand ([ed200ae](https://github.com/muslewski/token-oracle/commit/ed200ae599404b43714b5e2ba666b28a23ce85a2))
* **cli:** statusline headline with  cost + safe --install ([b6f9bfa](https://github.com/muslewski/token-oracle/commit/b6f9bfa9e61a641a393d673918cbc3777136482e))
* **cli:** surface real data toggle in doctor live row (compact marker) ([3128ef2](https://github.com/muslewski/token-oracle/commit/3128ef2ffb356093af307804b33e1db9066b1456))
* **colors:** sparkline, ARROW, gauge_bar, help_paint (one palette) ([5850dc8](https://github.com/muslewski/token-oracle/commit/5850dc87928a41047f61cc5bec45914378ef03ab))
* **config:** add live.headed setting + headed_enabled() + atomic update_config_file ([ba1ca92](https://github.com/muslewski/token-oracle/commit/ba1ca921694157d5e33e6b7f10253273cc882450))
* **core+live:** observed-rate bounded forecast + trusted fill authority (plan 063 T2,T4) ([c38f146](https://github.com/muslewski/token-oracle/commit/c38f146130d1905d58a0a216ef4260f418275425))
* **core+live:** trust gate + self-calibrating cap (plan 063 T1,T3) ([46d9067](https://github.com/muslewski/token-oracle/commit/46d90678909e909f81ff6672cfa8c398c94d1492))
* **core:** cached_events read-only seam in engine ([5482df4](https://github.com/muslewski/token-oracle/commit/5482df44d59824aaf650eeecdea0ace04c49d19d))
* **core:** pricing snapshot + cost modes + plan presets ([65eb8ba](https://github.com/muslewski/token-oracle/commit/65eb8ba99393a5976f665ce86385e7756f7602f7))
* **core:** report aggregation core (report.py + tests) ([c3b522b](https://github.com/muslewski/token-oracle/commit/c3b522b6f56c23f0b58509d61e88edea9410cb43))
* **core:** self-ingest Claude rate-limit header for live 5h ([f4e57e0](https://github.com/muslewski/token-oracle/commit/f4e57e0eb328fc681a37c20b7b738b5d148824c7))
* **dash:** add _fit_join width-budget helper (builds to fit; never trailing sep) ([50cf101](https://github.com/muslewski/token-oracle/commit/50cf101de74eb58950c662cd823fbfaaa24dc9a8))
* **dash:** add BARS_MIN and _bars_bar_w_for for narrow borderless bars ([31d2f18](https://github.com/muslewski/token-oracle/commit/31d2f1847acb10cf2b0e6ca163cef0a2a80eb557))
* **dash:** add fixed-region Scene, Region, Painter and ANSI helpers ([5ff39cb](https://github.com/muslewski/token-oracle/commit/5ff39cbc34b11a77b3a5fb9e20b249a5cd858289))
* **dash:** add glance floor (single-line worst-per-provider) between oneline and tiny ([32606b7](https://github.com/muslewski/token-oracle/commit/32606b77692a9ba0f3110f81fca8e124f43c0cae))
* **dash:** animate bar on % change — smooth glide + pulse (real-time UX) ([aa23e32](https://github.com/muslewski/token-oracle/commit/aa23e325b5ea1ba039e46503d8423134d83f3d4e))
* **dash:** blend live sources — local real-time 5h, web only for slow caps ([39edd68](https://github.com/muslewski/token-oracle/commit/39edd6895b16561a7523c659ca48bddc4a064979))
* **dash:** borderless slider bars renderer + wiring for 16..33 width ([b488017](https://github.com/muslewski/token-oracle/commit/b4880175f7755d3fb2dd9b032e9245d7f13a45b3))
* **dash:** fixed-height layout primitives and 3-line-per-window contract ([a2f21ab](https://github.com/muslewski/token-oracle/commit/a2f21abac9a5ce3c1709c67def2a6583a4e562b5))
* **dash:** Future tab live-aware cap-race UX (plan 062) ([8b0c8c4](https://github.com/muslewski/token-oracle/commit/8b0c8c4ee9f1d7d148c5c248db67b2b7b49c8643))
* **dash:** Future/Past honesty UX (plan 064) ([3b76f71](https://github.com/muslewski/token-oracle/commit/3b76f7151df433a9e9b6559c4c41db0a497e9add))
* **dash:** height-adaptive layout — degrade gracefully on short terminals ([bf3b5cc](https://github.com/muslewski/token-oracle/commit/bf3b5cc5e8a59f4a271f5db2f691c916155ccf27))
* **dash:** honest provenance 3-line rows + fixed scene composition in render_frame ([794bbf7](https://github.com/muslewski/token-oracle/commit/794bbf75189fe445cb45dda849f6334d2a08dd18))
* **dash:** Past ledger + Future prophecy tabs (019/020) ([8d0cfd5](https://github.com/muslewski/token-oracle/commit/8d0cfd598ca2e09073474c7fa259d03a6375e7bd))
* **dash:** priority-order + fit the compact line to width ([cde1f11](https://github.com/muslewski/token-oracle/commit/cde1f111664a2f869c0bfdd0e6d5517d17bc66a6))
* **dash:** run() uses Painter + routes probe ring + reset-&gt;alert ([75c328b](https://github.com/muslewski/token-oracle/commit/75c328b33f5adbfe1115b8dc3e301f04c53a5516))
* **dash:** tabbed TUI shell with keyboard input (plan 018) ([f1ed903](https://github.com/muslewski/token-oracle/commit/f1ed9033e0a97c5bc2999fd0ad872e9208a86bd8))
* **doctor:** config provenance, source data probe, cache health, exit code ([868fca8](https://github.com/muslewski/token-oracle/commit/868fca805ecb8914e69c0578fc16be07de369edf))
* **engine:** live-fill write-through skeleton (pre-063 checkpoint) ([bdc0614](https://github.com/muslewski/token-oracle/commit/bdc061449523bb38149c1d05c60a2fc66d239b54))
* give engine single-source path scan fallback on failure (plan 041 step 3) ([6c0f2ea](https://github.com/muslewski/token-oracle/commit/6c0f2eab0d1a0cc72b4dbeb1859f15621f20a484))
* harden claude_code iter_usage_events to skip malformed JSONL lines (plan 041 step 1) ([c9733f6](https://github.com/muslewski/token-oracle/commit/c9733f624da400bf8f9d090e5e7f4b65aec3ca4f))
* harden grok iter_total_tokens_reports to skip malformed JSONL lines (plan 041 step 2) ([1306bc8](https://github.com/muslewski/token-oracle/commit/1306bc840373f1932e9c30c9a6bb9ccb73168b2f))
* **install:** add POSIX curl|sh installer (plan 047) ([ace8552](https://github.com/muslewski/token-oracle/commit/ace85529298ee1bacd17ec9d9fdd024589ec4f7f))
* **live:** add atomic store.py for live.json snapshot (save/load, default path) ([9075ea1](https://github.com/muslewski/token-oracle/commit/9075ea1dff408bd89066da6097acee9e9627f97f))
* **live:** add legacy adapter + overlay; route dashboard exclusively through LiveCell/overlay (no direct fetch in render) ([bbe4623](https://github.com/muslewski/token-oracle/commit/bbe46238f78c96853ddfa111729521f81dae45f1))
* **live:** add oracle live-probe subcommand and token_oracle.live.probe.run_probe; probe is only active path; doctor/dash no longer bootstrap; json + summary + exit codes ([0be22a9](https://github.com/muslewski/token-oracle/commit/0be22a9ecf9ff1702e7b9da9a300df27737c4d8c))
* **live:** add virtual_display() context manager for shared headed display lifecycle (RC-A restore, RC-C stderr progress) ([5ac0ae0](https://github.com/muslewski/token-oracle/commit/5ac0ae0c34c1a8551f5b20ecc7a03e7260d5b7cf))
* **live:** dashboard run() uses background subprocess worker for live-probe; every frame reads load_snapshot + overlay_cells; no in-process probe or startup banner ([8a9519b](https://github.com/muslewski/token-oracle/commit/8a9519bdab8394156d5cda26ef986343dfa0101d))
* **live:** doctor live section now reads snapshot via get_live_status; instant, no browser launch or progress text ([843f6a6](https://github.com/muslewski/token-oracle/commit/843f6a6b0c4ab5f67d975c9fd251ffc7a4b11979))
* **live:** grok live weekly usage via ?_s=usage modal ([0faeaf4](https://github.com/muslewski/token-oracle/commit/0faeaf4bf7e0a233a7fa5bc0e7f04a68a8156ac1))
* **live:** handle Cloudflare bot challenge in fetchers ([f8ff0f9](https://github.com/muslewski/token-oracle/commit/f8ff0f9bfb116c8a260bf5e67d1e809ee0b8e90a))
* **live:** honest retained/stale provenance + upward misparse guard (plan 063 T5, I4) ([a51b364](https://github.com/muslewski/token-oracle/commit/a51b364c891f62dfbcb237cbe653c362cdfea077))
* **live:** introduce grok_extract.py with evidence-bound pure extractors ([ab891cb](https://github.com/muslewski/token-oracle/commit/ab891cbab6187c0a67b1b302a11fd6b508934c22))
* **live:** introduce typed LiveReading/ProviderLive contract with to/from_dict helpers ([2f680d3](https://github.com/muslewski/token-oracle/commit/2f680d3198309767b394d05e7790c4160997d917))
* **live:** live web scraper, grok source, multi-profile dash wiring (WIP base) ([c24145c](https://github.com/muslewski/token-oracle/commit/c24145ca663994116ed4918d414b343a092eb14c))
* **live:** ProgressFn + _emit to stderr; get_live_status snapshot-derived (now=None); delete _LIVE_CACHE, TOKEN_SILENT prints and env hack; fetchers take progress kwarg ([33af788](https://github.com/muslewski/token-oracle/commit/33af788c1f47cae9a3cf0e5c91a2ac38471a4013))
* **live:** Step 1 - claude_extract.py (row-scoped classify/readings/five_hour/distinctness) + extract_common.py (moved merge/monotonic/build + provider-aware) + grok_extract reexports ([209d083](https://github.com/muslewski/token-oracle/commit/209d0834fb1d2d09cf46fe02572ef9eb8365c3af))
* **live:** surface weekly from rate-limit header as a live cell ([3178ff7](https://github.com/muslewski/token-oracle/commit/3178ff73409f1366467c7dbcf2b135faec5052d0))
* present-truth anchoring + Future/Past honesty (063/064) ([fdfee93](https://github.com/muslewski/token-oracle/commit/fdfee93eeee4edf7279495af434a5db53ed44d26))
* **shim:** add npm/ package for npx token-oracle / bunx ([eda8547](https://github.com/muslewski/token-oracle/commit/eda854751eae6a35fa8e96eb5f7f8da97481febe))
* snapshot write-through (015) + agentic-sage doctor detect (022) ([5456f29](https://github.com/muslewski/token-oracle/commit/5456f295c62e6e3c9ea35fb3ef9834e4f19881c6))
* **sources:** carry model + token classes in events ([9e9f57f](https://github.com/muslewski/token-oracle/commit/9e9f57f1e9628e6a55992565442a0bede71066a8))
* **sources:** discover third-party adapters via entry points ([2d0f380](https://github.com/muslewski/token-oracle/commit/2d0f380986c406159cb1b80e0702f23c07ebc483))


### Bug Fixes

* **cli:** add __main__ guard so python -m invocation works (probe worker fallback path) ([74bc07e](https://github.com/muslewski/token-oracle/commit/74bc07eeb56dbe2ec808be79bcd4b4553e82a3de))
* **colors:** preserve ANSI when box_line truncates (no more white text on narrow) ([3a0c4f5](https://github.com/muslewski/token-oracle/commit/3a0c4f5464649dafd3c43a15c46848e54fc78b29))
* **config:** tolerate non-string cache_path ([c278ed4](https://github.com/muslewski/token-oracle/commit/c278ed4b2d64909d775b90b5f8ea4457eed948c5))
* **config:** validate window entries, never raise on malformed config ([e0d1869](https://github.com/muslewski/token-oracle/commit/e0d1869d0ff51b529ba3cc263a1dc49506e8c805))
* **core:** real-data verification — bound projection by consistent burn, flat 5h (plan 063 I2) ([805ec60](https://github.com/muslewski/token-oracle/commit/805ec60f7c2ff0e2ca7b33842440f1fd28c37233))
* **dash:** align box borders (wide-char width) + width-1 icons + cleaner labels ([ca99c7a](https://github.com/muslewski/token-oracle/commit/ca99c7a9a125310fac6331f1418fc9fb27500dd7))
* **dash:** ANSI in-place repaint instead of os.system("clear"); drop unused now param ([91596a0](https://github.com/muslewski/token-oracle/commit/91596a0fefbe3352f5cb82022c77ab5e63f91d81))
* **dash:** color-safe cell-aware truncation in Scene.render ([cbaa11e](https://github.com/muslewski/token-oracle/commit/cbaa11ec42de0635eae7806f7bd4289024d6cf5f))
* **dash:** derive panel width + arrangement from terminal width ([98a6845](https://github.com/muslewski/token-oracle/commit/98a6845ef594bc36299b055341997601228fbbb8))
* **dash:** erase ghost rows on variable-height tab switch ([1bd53e7](https://github.com/muslewski/token-oracle/commit/1bd53e797c214a06da4b9c4c29da24a4598b7da6))
* **dash:** glance floor orders by % desc, pct-first (binding survives narrow) ([66e436d](https://github.com/muslewski/token-oracle/commit/66e436de0d4730a13b70fa5725106cd135ea441f))
* **dash:** make gauge bar and profile block width-parametric ([2c73082](https://github.com/muslewski/token-oracle/commit/2c730829d163ec7ccfa10d126584928d9bf92077))
* **dash:** Past overflow/flicker + faster present-first load path ([d117400](https://github.com/muslewski/token-oracle/commit/d11740034fe80bc6dd504615b6483245a7c249e5))
* **dash:** symmetric header chips — drop the age suffix ([3e1e4f0](https://github.com/muslewski/token-oracle/commit/3e1e4f07b86a64e1cbc7b92dac4ab63ae2761326))
* **demo:** move bootstrap env out of VHS Hide blocks ([eaab328](https://github.com/muslewski/token-oracle/commit/eaab328d565a176144497b970275ac90fa92e008))
* **engine:** multi-profile forecast must not save_cache every call ([264e5d5](https://github.com/muslewski/token-oracle/commit/264e5d55d31788d0fc3af245b6b2b1d822a32a83))
* **io:** unique temp files for atomic writes; snapshot failure exits non-zero ([5f38fa0](https://github.com/muslewski/token-oracle/commit/5f38fa06225709304d396a425b0335c8f12ad90b))
* **live:** collect atomic per-meter claude rows so Fable is not swallowed ([448b547](https://github.com/muslewski/token-oracle/commit/448b5471cece5568fc1d46406f866aabc58fa93a))
* **live:** defensive split_multi_meter_rows so merged claude rows never swallow Fable ([bff1ab8](https://github.com/muslewski/token-oracle/commit/bff1ab8abcb952105def202974241063e127cf9e))
* **live:** grok driver now thin fact collector around evidence-bound extractors ([a3a29f3](https://github.com/muslewski/token-oracle/commit/a3a29f38bf6120d4945afbd1bfd6125cc79008f4))
* **live:** launch_login_session now uses virtual_display CM; delete dead _maybe_start_virtual_display (RC-C) ([cc38a46](https://github.com/muslewski/token-oracle/commit/cc38a46e4c0f40bd3c6b82bbc9323a3f8153f278))
* **live:** legacy grok path is now passthrough for native ProviderLive ([cb12259](https://github.com/muslewski/token-oracle/commit/cb122594515a341d61affbfc7b924f170675c367))
* **live:** network-json allowlist strict — exact keys + used/limit pair only ([0247cf3](https://github.com/muslewski/token-oracle/commit/0247cf354c07bb84df84c729664262392e6b4052))
* **live:** own virtual display once per run_probe via context manager; emit honest unavailable instead of needs_login lie (RC-A, RC-D) ([142153f](https://github.com/muslewski/token-oracle/commit/142153f82cee2889497bf5898c617d5ffd5e0c12))
* **live:** remove per-fetch xvfb lifecycle from fetch_*_live_usage; add headed preflight returning unavailable (RC-A, RC-D) ([d9451d0](https://github.com/muslewski/token-oracle/commit/d9451d0533db5a0233a67c040fb9ae6146f7dffa))
* **live:** Step 2 - rewrite fetch_claude_live_usage to row-scoped + network listener; delete legacy.py; update call sites (cli/dash) + tests ([b37e38f](https://github.com/muslewski/token-oracle/commit/b37e38fc89b665f055e156625b5cdc2075340c9e))
* **live:** stop cap cells going stale between probes (TTL vs interval) ([5093591](https://github.com/muslewski/token-oracle/commit/50935914bc2a84e9d577146040bbe5a4c64e6448))
* **live:** weekly header must be FRESH (&lt;600s) to touch forecast math (plan 063 I3) ([866dd87](https://github.com/muslewski/token-oracle/commit/866dd87b65db1de46197541cbd855fe46576daf1))
* quality-pass Grok 4.5 revise of DONE advisor plans ([a3a5516](https://github.com/muslewski/token-oracle/commit/a3a55165cbe9dc94ddfdfbbe63a5388ddfe95c7b))
* satisfy ruff/mypy after validator addition (plan 039) ([af180b8](https://github.com/muslewski/token-oracle/commit/af180b872c36e7e6f7dca00d6ecab114a8e0bf64))


### Performance Improvements

* **assets:** serve avif/webp banners via &lt;picture&gt; ([e39ea3a](https://github.com/muslewski/token-oracle/commit/e39ea3a0699223457ad02ddaa7ef7196cc497417))
* **dash:** decouple UI from data — skeletons + background worker ([3e19d37](https://github.com/muslewski/token-oracle/commit/3e19d37c833022463e1626336d05392496fd8b8f))


### Documentation

* add adapters banner to ADAPTERS.md ([9b8db04](https://github.com/muslewski/token-oracle/commit/9b8db04297c8396bef1b3451536c35104685fbc3))
* add hero banner to README ([15d9e29](https://github.com/muslewski/token-oracle/commit/15d9e29da1285b822b2fcada44f24b83a605eb71))
* cache-bust README badges to force camo refresh ([d2b4d32](https://github.com/muslewski/token-oracle/commit/d2b4d32a36b659863d764760ff698eca07e1e087))
* CLI surfaces to dash-quality spec (fleet phase 4) ([2e35824](https://github.com/muslewski/token-oracle/commit/2e358240787c378570f70807ed00810f576d7bbd))
* **demo:** add staged README demo harness for token-oracle ([1c5f4b0](https://github.com/muslewski/token-oracle/commit/1c5f4b09be56180e52ee99380d0e78e96e06b06f))
* **demo:** commit regenerated staged demo GIFs ([65fd71d](https://github.com/muslewski/token-oracle/commit/65fd71db48f1b546483f4fa86799bb08f85d1c22))
* fix config format, generic-source, colors, and import-namespace drift ([d5028af](https://github.com/muslewski/token-oracle/commit/d5028af3068462f9338ec3075094b31f211d0785))
* **plans:** 031/032 sequential, not parallel (shared web.py plumbing) ([3ede271](https://github.com/muslewski/token-oracle/commit/3ede27154fe93286e0c85a5dcb0d9c1013623594))
* **plans:** 035 DONE — merged at f337ca2, RC-A/C/D verified end-to-end ([aa2ecd0](https://github.com/muslewski/token-oracle/commit/aa2ecd017c34dc6384698e12498ffb615b6c080b))
* **plans:** 036 DONE + plan 037 (claude Fable weekly row separation) ([e3a7a8f](https://github.com/muslewski/token-oracle/commit/e3a7a8fe4ba4140231d16d4f41ebf9cf4156e063))
* **plans:** 037 DONE — headed-real-data round complete at 98f364c ([5f5bfad](https://github.com/muslewski/token-oracle/commit/5f5bfadcb0c87bf482111be33dc8da28b1f34226))
* **plans:** 062 Future tab live-aware cap-race UX design ([367a362](https://github.com/muslewski/token-oracle/commit/367a362a5f29a82b7ff7850a6c007883ae6f8b7c))
* **plans:** 063 + 064 → DONE with commit ranges ([93ad8fc](https://github.com/muslewski/token-oracle/commit/93ad8fc432a36440788bd8443ad529242c78b62d))
* **plans:** 063 engine-truth + 064 Future/Past-UX plans + design ([301587a](https://github.com/muslewski/token-oracle/commit/301587a5f35f0b1a632e895660a68a1c9ff7c3f6))
* **plans:** add 052/053/054 (width-responsive, self-ingest ratelimits, weekly-via-header); mark 051 DONE ([111cbc4](https://github.com/muslewski/token-oracle/commit/111cbc4c9e01bf0bf81179d964a41ceb23afd7c1))
* **plans:** add 055 (box_line color-preserving truncation), mark DONE ([4e68175](https://github.com/muslewski/token-oracle/commit/4e68175e11bdc5b3be5bb0b0c40857ee4babaf2a))
* **plans:** add 056 (low-width triage), mark DONE ([b6bf30e](https://github.com/muslewski/token-oracle/commit/b6bf30e31f1f91581a94c2b733bf368315906b84))
* **plans:** add 057 (narrow borderless bars), mark DONE ([bd54990](https://github.com/muslewski/token-oracle/commit/bd549905dbde368148c9616bdaed50572aee853b))
* **plans:** add 058–060 (sticky-hooks round) ([b5092bc](https://github.com/muslewski/token-oracle/commit/b5092bcf057ac09f53cde049ccf1a5a9200e9440))
* **plans:** headed-real-data round (035 display lifecycle, 036 live toggle) ([7d70582](https://github.com/muslewski/token-oracle/commit/7d70582c6a106a0e855e94be3947208ce20a22a0))
* **plans:** live-truthfulness round 030-034 + index reconcile ([f8d6fed](https://github.com/muslewski/token-oracle/commit/f8d6fed6b85c24ae0c71a02184324813769231c6))
* **plans:** live-truthfulness round completed at 4509a22 ([059ad33](https://github.com/muslewski/token-oracle/commit/059ad339332921d4b2be9643fce3339337388f3c))
* **plans:** mark 034 done (fixed-region scene, provenance, tests) ([24b4b77](https://github.com/muslewski/token-oracle/commit/24b4b77906d92941912b05f25d6149e046ed2ea9))
* **plans:** mark 039/040/041 DONE — Phase-0 truthfulness gate cleared ([7264a71](https://github.com/muslewski/token-oracle/commit/7264a7144ed659c01fcca131142f92c9384c6f10))
* **plans:** mark 042/043/044/045 DONE — Phase 1 (make it visible) merged ([e0d8384](https://github.com/muslewski/token-oracle/commit/e0d8384a6edb3c94752b2af613618fcb3545acba))
* **plans:** mark 046/047/049 DONE (Phase 2) + plan 051 (fallback-test hermeticity) ([41f53f3](https://github.com/muslewski/token-oracle/commit/41f53f3dcc7585982f1b7bc74fa1feecda34502e))
* **plans:** mark 052/053/054 DONE (merged + pushed) ([d52d7b7](https://github.com/muslewski/token-oracle/commit/d52d7b78ac84da9671f9c3c8538004cac9d01507))
* **plans:** mark plan 032 DONE in README.md (final commit per plan) ([160346d](https://github.com/muslewski/token-oracle/commit/160346d940e9af1b397072b471dbae12f6db2831))
* **plans:** mark plan 033 DONE; 189p/1s; all gates + verifies honored ([55cd25f](https://github.com/muslewski/token-oracle/commit/55cd25ff8577adb26786c05c32f65c0afb781b9a))
* **plans:** Phase 1 (make it visible) — plans 042/043/044/045 ([e8b7f22](https://github.com/muslewski/token-oracle/commit/e8b7f22281b860f10f6c20fac9fa363eff92e228))
* **plans:** Phase 2 (make it spread) — plans 046/047/049/050 ([adb71a6](https://github.com/muslewski/token-oracle/commit/adb71a6826701b64d721594401d8c10e37ded656))
* **plans:** Phase-0 truthfulness gate — plans 039/040/041 ([537f8e3](https://github.com/muslewski/token-oracle/commit/537f8e30e6eac78b5d2008dac500ea59e30be2d9))
* **readme:** embed animated dashboard demo (plan 045) ([74b2ce0](https://github.com/muslewski/token-oracle/commit/74b2ce04eb237aab2bb6fc80b1f68a5edf46d04f))
* **readme:** rewrite Install section for npx/bunx/curl + uv/pipx/pip (plan 049) ([4a089e5](https://github.com/muslewski/token-oracle/commit/4a089e59487060aa40b8f411d4545b3d2d81b10b))
* **readme:** wire staged demo GIFs per fleet embed contract ([9726029](https://github.com/muslewski/token-oracle/commit/97260299223b381ae8d9969a737be40bd557d401))
* statusline --install one-liner + status bar section ([9dbccd5](https://github.com/muslewski/token-oracle/commit/9dbccd55484d7aa961e89cbcb337a1459c5a539a))

## [0.1.1](https://github.com/muslewski/token-oracle/compare/token-oracle-v0.1.0...token-oracle-v0.1.1) (2026-06-30)


### Features

* **adapters:** thin statusline + tmux reference renderers ([9050cfb](https://github.com/muslewski/token-oracle/commit/9050cfb0a3399bea45233d5aff02019480cfa83d))
* **cli:** oracle forecast/snapshot/statusline/tmux/doctor/dash ([f0144e8](https://github.com/muslewski/token-oracle/commit/f0144e82b04efce0e2da71f3c0f518219e1ddd91))
* **colors:** central palette, gauge thresholds, terminal gating ([21fd5a3](https://github.com/muslewski/token-oracle/commit/21fd5a361d324834cf6112e10396b08155e16be5))
* **core:** atomic aggregation cache + event collection ([8b04b4c](https://github.com/muslewski/token-oracle/commit/8b04b4cbe7a691909734052ed47bc59782b80a91))
* **core:** config loader + max20 preset + XDG paths ([b3cec08](https://github.com/muslewski/token-oracle/commit/b3cec08f89bb6fee86c2da7fabe6c8bf6632b1c5))
* **core:** forecast facade orchestrating source-&gt;cache-&gt;windows ([a058dc8](https://github.com/muslewski/token-oracle/commit/a058dc81bd5b8d82ccb3853cbe1c7562039657dc))
* **core:** generalized window forecast + eta_to_cap ([9c651e1](https://github.com/muslewski/token-oracle/commit/9c651e1fecefc6bd4d328a7f17bbb16083e32b92))
* **core:** neutral UsageEvent/Window/Forecast contracts ([d96370b](https://github.com/muslewski/token-oracle/commit/d96370bd1327f2f9c6f2d841ff78c3d793657876))
* **core:** pattern-aware burn profile (decay + EB shrinkage) ([4126292](https://github.com/muslewski/token-oracle/commit/4126292568f2053f0b46cf06130e0b3f942a0148))
* **core:** time parsing + display formatters ([580ff24](https://github.com/muslewski/token-oracle/commit/580ff2418bb46cc83765453d767c4ed2b9966da4))
* **dashboard:** minimal stdlib forecast TUI ([7997d01](https://github.com/muslewski/token-oracle/commit/7997d012ebdfcb49072f9bf03f8cd70d5f964354))
* **dash:** colored block-bar TUI with violet header, dim metadata ([98ff6e1](https://github.com/muslewski/token-oracle/commit/98ff6e13be5dac0a61d45be9309275035b87e9d2))
* **doctor:** badge rows with real checks + ok/attention footer ([585160f](https://github.com/muslewski/token-oracle/commit/585160f1febf1bc0ccd7bde038be96fe178f24a5))
* **install:** reversible non-clobbering installer + uninstaller ([eda808c](https://github.com/muslewski/token-oracle/commit/eda808cd551cb0254e401fa38d0494a2b252d87c))
* rename importable package oracle → token_oracle; add token-oracle console script ([041e6de](https://github.com/muslewski/token-oracle/commit/041e6dec7c73e3b00954b40db48f11960b8f0d40))
* scaffold token-oracle package + packaging ([35c598b](https://github.com/muslewski/token-oracle/commit/35c598b9d8087fe47472d21d0fa39ca50c31d8d5))
* **snapshot:** versioned forecast.json contract writer ([2dd9330](https://github.com/muslewski/token-oracle/commit/2dd93308b51896cb58e2c38d2f844e1af6a2f081))
* **sources:** generic stub source for custom feeders ([c049f9d](https://github.com/muslewski/token-oracle/commit/c049f9d024703535b72a66031c6641bfa31c3f8c))
* **sources:** source registry + claude_code adapter ([a3ea851](https://github.com/muslewski/token-oracle/commit/a3ea8510fd0dee83f25bc4ef6e2db4957a36e9aa))


### Bug Fixes

* correct author attribution to Mateusz Muślewski ([a3ff011](https://github.com/muslewski/token-oracle/commit/a3ff011ba92aa2d3c33ad6ef81ca982a6e01fb2c))
* correct README to real CLI surface, publish trigger, command-name coherence ([98dce68](https://github.com/muslewski/token-oracle/commit/98dce6845b550ff0770a23a19475d9b345729fb2))
* **engine:** cache events for warm replay (source-agnostic); annotations, doc counts, hidden --now ([886c296](https://github.com/muslewski/token-oracle/commit/886c2966c59fec29ed7042ee117a5b754f5b305a))
* **sources:** bound scan output to [now-window, now]; gitignore bytecode ([6f60f00](https://github.com/muslewski/token-oracle/commit/6f60f003b7cf0358a63917c674f7270e62f9dcc1))


### Documentation

* add repo hygiene — CONTRIBUTING, CoC, SECURITY, templates, dependabot, CHANGELOG ([bfec45e](https://github.com/muslewski/token-oracle/commit/bfec45ef1f2fc4b92730762a1e841deb7a62f7f9))
* polished README (badges, acronym tagline, colors section) ([6acbff3](https://github.com/muslewski/token-oracle/commit/6acbff3f55abeb65deb56f5744237efb6bd60f5b))
* presentation-polish design spec ([b0de524](https://github.com/muslewski/token-oracle/commit/b0de524cb4a56c6ae90b118dcc215d2523260beb))
* presentation-polish implementation plan ([0e8dafd](https://github.com/muslewski/token-oracle/commit/0e8dafdc52286a0ff91d2bc611a4aeee805f710a))
* README, SETUP, AGENTS, ADAPTERS ([23204d9](https://github.com/muslewski/token-oracle/commit/23204d9f30b0fe34f5d41dc02edfee26768edb07))
* rewrite README — badge row, how-it-works, token-oracle command, fix copyright ([c98995f](https://github.com/muslewski/token-oracle/commit/c98995f69f4252ca1d8ace9adf0b805576a1d6e8))
* rewrite README from authoritative spec (badges, install, dify structure) ([99c6aa8](https://github.com/muslewski/token-oracle/commit/99c6aa8d6dd9971cf30db03b4c7b6adbf7492182))
* tighten Task 13 statusline test assertion ([880df8e](https://github.com/muslewski/token-oracle/commit/880df8ec681c7cc4814397f27e083b1274ecfe0c))
* token-oracle design spec ([bfc71a9](https://github.com/muslewski/token-oracle/commit/bfc71a906ce09f16de49c2bab7d91f40bb2cd429))
* token-oracle implementation plan (16 tasks, TDD) ([1f95caf](https://github.com/muslewski/token-oracle/commit/1f95caf1a514f4c13fcd34cadd4deabbe12a418d))

## [Unreleased]

### Added
- First-class `grok` source for Grok Build CLI (`~/.grok/sessions/.../updates.jsonl` totalTokens deltas)
- Neutrality: generalized docs, examples, AGENTS.md, doctor for Claude Code + Grok Build + generic
- Grok wiring: config examples, tmux bottom-bar support, hook integration for snapshots
- `tests/test_sources_grok.py`; adapter pattern remains easy to extend for cursor/windsurf/etc

### Changed
- Docs/README/SETUP/AGENTS now frame as multi-agent (no Claude lock-in in UX)
- Source registry, defaults, and examples updated while preserving 100% Claude compat
- `oracle tmux` / `statusline` now first-class for Grok users in tmux / status areas

## [0.1.0] — 2026-06-30

### Added

- Initial release: provider-agnostic token usage-cap forecaster
- Claude Code source adapter (reads `~/.claude/usage/` JSONL logs)
- Generic sliding-window forecast engine
- Tmux and statusline output adapters
- Interactive dashboard (`token-oracle dashboard`)
- Doctor command (`token-oracle doctor`)
- 71 unit tests; zero runtime dependencies

[Unreleased]: https://github.com/muslewski/token-oracle/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/muslewski/token-oracle/releases/tag/v0.1.0
