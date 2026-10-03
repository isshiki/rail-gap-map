# Agent instructions

## Purpose and boundary

`rail-gap-map` is an independent, public personal project linked to a personal blog. It maps walking distance to the nearest railway station as isolines, to show areas far from stations. Use only publicly obtainable data and public sources.

- **会社（非公開）→ rail-gap-map（個人公開）は禁止。** Do not access, reference, copy, or import company repositories, private code, internal documents, prompts, configuration, proprietary logic or know-how, or nonpublic/commercial data (e.g. ロケスマDATA, company fact databases or MCP servers). Do not explore sibling company projects for context.
- **rail-gap-map（公開）→ 会社側の参照は可。** This does not authorize importing company assets here.

## Public safety

- Never commit raw/downloaded data, credentials, `.env`, databases, or caches. Do not force-add ignored files. Raw downloads go to `data/raw/`, caches to `data/cache/`, intermediate builds to `data/build/`.
- The only generated data committed is the small web output under `web/data/`, after its license (ODbL / CC BY derived) is documented in `docs/data-policy.md`.
- Before using a new source, document license, attribution, redistribution conditions, official source, version, and review date in `docs/sources/`. Pin versions (dated snapshots), record retrieval date (UTC) and SHA-256.
- **Ask the user before every download**, stating file name, source URL, and size.
- Before every `git add` / `git commit`, inspect status, candidate paths, sizes, and contents. Investigate any file over 1 MiB. Review the staged diff before committing.
- **Ask the user before every `git push`.**
- Code and original documentation: Apache-2.0. External data keep their own licenses.

## Development

Python 3.11+ with uv. Add dependencies only with `uv add`; commit `uv.lock`. Keep `src/ekiwalk/` free of app-specific code so a second app (station catchment: "which station's walking area am I in") can reuse it. The web app is static (no build step) and must not send user locations anywhere.

## Local workflow (any AI agent or human contributor)

- Use these instructions independently of any particular AI product or plugin. Do not require product-specific skills or commit signatures.
- Work on a branch created from `main`. After user approval, merge with fast-forward only and ask before pushing. Verify the Pages deployment after an authorized push.
- Do not access or modify `C:\Projects-GitHub\eki-walk`; it is a separate active project.
- Follow [README.md](README.md) for current commands. `docs/superpowers/` preserves historical designs and plans; embedded code and unchecked tasks are not the current implementation or a request to redo it.
- Prefer existing dependencies and data for validation: `uv run --offline --frozen pytest -q` and `node --test web/test/lookup.test.js web/test/search.test.js`. Do not install dependencies or fetch data implicitly during validation.
- Start the local web server with `powershell -NoProfile -File scripts/serve.ps1`; it binds to loopback only and needs no editor-specific launch configuration.
- For display or interaction changes, verify Tokyo and Osaka in a browser at desktop width and 375 px width, including scenario switching, search, and the mobile sheet.
