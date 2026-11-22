# Contributing

## Local setup

1. Install Python 3.12 or 3.13, `uv`, and Node.js 22.
2. Run `uv sync --all-groups` from the repository root.
3. Run `npm ci` from `web/`.
4. Run `uv run pytest` and `npm test` before opening a pull request.

## Pull requests

- Keep changes focused and describe the data behavior they affect.
- Add a fixture or test when changing ingestion, model contracts, or dashboard data handling.
- Never commit downloaded TLC records, credentials, or generated database files.
- Include the output of `uv run dbt build` when changing warehouse models.
