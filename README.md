# astro-proj

An astrophotography stacking app: a Python/FastAPI backend does raw-frame
calibration, star alignment, and stacking; a Tauri + React desktop frontend
(`astro-stacks/`) drives it and lets you interactively adjust the stretch on
the result.

```
astro-proj/
├── api.py                 FastAPI app: HTTP endpoints over the pipeline package
├── pipeline/               Stacking pipeline (calibration, alignment, stacking, color, stretch, halos, workspace store)
├── tests/                  pytest suite, runs against synthetic data (no real captures needed)
├── astro-stacks/           Tauri + React + TypeScript frontend (Chakra UI + Sass modules)
├── debug_stars.py          Standalone script: visualize ORB star detection on a frame
├── stacking_datasets/      Developer dataset directory. Datasets are large so we ignore the contents.
├── requirements.txt        Backend runtime dependencies
├── requirements-dev.txt    Backend dev dependencies (adds pytest)
└── PythonDocs.md           Backend environment cheat sheet (venv activate, freeze, uvicorn)
```

Everything is organized around **workspaces**. A workspace points at a frames
folder anywhere on disk (must contain a `lights/` subfolder, optionally
`darks/`, `flats/`, `biases/`) — the folder is referenced in place, never
copied, since real capture sessions can be many gigabytes. Each workspace's own
bookkeeping (the stacked linear master, saved version exports, metadata) lives
under `astro-stacks/workspaces/<workspace-id>/`, kept separate from your
capture data. Create a workspace from the app's "New Workspace" button (native
folder picker in the desktop app; a plain path field when running in a
browser), or via `POST /workspaces`.

## Prerequisites

| Tool | Used for | Notes |
|---|---|---|
| Python 3.11+ | backend | `rawpy` needs a recent CPython; project was verified on 3.14 |
| Node.js 18+ and pnpm | frontend | `pnpm` is what the Tauri config invokes (`pnpm dev`, `pnpm tauri dev`) |
| Rust toolchain (`rustc`, `cargo`) | frontend desktop shell | only needed to run/build the Tauri desktop app, not for browser-only frontend work |

Install pnpm if you don't have it: `npm install -g pnpm`.
Install Rust via [rustup](https://rustup.rs/) if you don't have it — required
for `tauri dev` / `tauri build` (not required just to run the backend or use
`pnpm dev` for browser-only UI work).

## Getting started

### 1. Clone and set up the backend

```sh
git clone <repo-url> astro-proj
cd astro-proj

python -m venv venv
# Windows:
.\venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

pip install -r requirements-dev.txt   # runtime deps + pytest
```

`requirements-dev.txt` pulls in `requirements.txt`, so you get everything
needed to both run the API and run the test suite in one install. If you only
ever plan to run the app (no tests), `pip install -r requirements.txt` alone
is enough.

### 2. Set up the frontend

```sh
cd astro-stacks
pnpm install
cd ..
```

### 3. Point a workspace at your frames

You don't need to put anything inside the repo. Once the app is running (see
below), click "New Workspace" and give it a name and a folder — anywhere on
disk — containing a `lights/` subfolder (and optionally `darks/`, `flats/`,
`biases/`) with your raw frames (`.cr2`, `.cr3`, `.nef`, `.arw`, `.dng`) or
already-developed images (`.png`, `.jpg`, `.tiff`). The folder is referenced
in place, not copied.

## Running the dev environments

You need two things running at once: the backend API and the frontend.

**VS Code terminal setup**: `.vscode/settings.json` disables automatic venv
activation for new terminals (VS Code's Python extension otherwise activates
it in *every* new terminal, which gets in the way of `pnpm`/`npm`). Plain new
terminals are venv-free — good for frontend work. For backend work, open the
terminal dropdown (the chevron next to the `+` in the terminal panel) and
pick the **"Backend (venv)"** profile, which activates the venv on open.

**Terminal 1 — backend** (from the repo root, venv activated):
```sh
uvicorn api:app --reload
```
This serves on `http://127.0.0.1:8000`. Interactive API docs (Swagger UI) are
available at `http://127.0.0.1:8000/docs` — the fastest way to poke individual
endpoints (`/workspaces`, `/workspaces/{id}/pipeline/run`, `/workspaces/{id}/preview`, ...)
without the frontend.

**Terminal 2 — frontend**, pick one:

- Full desktop app (what end users get):
  ```sh
  cd astro-stacks
  pnpm tauri dev
  ```
  This launches the native Tauri window backed by a Vite dev server on the
  fixed port `1420` (configured in `src-tauri/tauri.conf.json`) with hot
  reload for both the UI and Rust shell.

- Browser-only, for iterating on the React UI without the Rust/Tauri build
  step (faster reload, no native window):
  ```sh
  cd astro-stacks
  pnpm dev
  ```
  Then open the URL Vite prints. The app talks to the backend at
  `http://127.0.0.1:8000` regardless of which frontend mode you use, so the
  backend must already be running.

The frontend's API base URL is hardcoded in `astro-stacks/src/api/client.ts`
(`API_BASE`) — change it there if you run the backend on a different host or
port.

### Theming

Every color in the app traces back to one file:
`astro-stacks/src/theme/colors.ts` (the `brand` scale). Chakra UI turns theme
tokens into CSS custom properties (`--chakra-colors-brand-500`, etc.), which
both Chakra components (via `colorPalette="brand"`) and every plain
`*.module.scss` panel read directly — so re-skinning the app is a one-file
edit, no component changes needed. Dark/light mode is a small custom
`ThemeModeProvider` (`astro-stacks/src/theme/ThemeModeProvider.tsx`, dark by
default, persisted to `localStorage`) that toggles a `dark`/`light` class on
`<html>`, which is the exact selector Chakra's built-in `_dark`/`_light`
semantic token conditions key off.

## Testing individual features

### Backend: automated tests

```sh
pytest
```

`tests/conftest.py` generates a small synthetic dataset (star field with
known positions, injected hot pixels, and a vignette) on the fly, so the
suite runs without any real capture data.

- `tests/test_pipeline.py` — each pipeline stage independently (calibration,
  flat normalization, color calibration, stretch methods, halo cleanup,
  alignment) plus full end-to-end `orchestrator.run_pipeline` runs (with/without
  calibration, both integration methods, custom `output_dir`) and regression
  tests for real bugs found along the way (numerical blow-up in flat-fielding,
  per-channel flat normalization, background-neutralization destroying signal).
- `tests/test_workspace.py` — workspace create/list/get/delete, running the
  pipeline into a workspace's own output directory, saving and listing versions.

Run a single test while iterating on one stage, e.g.:
```sh
pytest tests/test_pipeline.py::test_alignment_registers_shifted_frame -v
```

### Backend: testing against a real (or synthetic) dataset manually

For anything that needs to be eyeballed (does the stack actually look right?)
rather than asserted on, drive it through the running API:

```sh
# 1. start the backend (see above), then in another shell:
curl -X POST http://127.0.0.1:8000/workspaces \
  -H "Content-Type: application/json" \
  -d '{"name": "Rosette test", "source_path": "C:/path/to/RosetteNebula"}'
# -> {"id": "...", ...}

curl -X POST http://127.0.0.1:8000/workspaces/<id>/pipeline/run \
  -H "Content-Type: application/json" \
  -d '{"sigma": 3.0, "apply_dark": true, "apply_flat": true, "integration_method": "sigma_clip"}'
# -> {"job_id": "..."}

curl http://127.0.0.1:8000/workspaces/<id>/pipeline/status/<job_id>   # poll until "status":"done"

curl -X POST http://127.0.0.1:8000/workspaces/<id>/load_master

curl "http://127.0.0.1:8000/workspaces/<id>/preview?method=mtf&midtone=0.25" -o preview.jpg

curl -X POST http://127.0.0.1:8000/workspaces/<id>/versions \
  -H "Content-Type: application/json" \
  -d '{"note": "baseline run", "method": "mtf", "midtone": 0.25}'
```

Or just use `http://127.0.0.1:8000/docs` and run these calls from the browser.

If you don't have a real dataset handy, generate one with the same frame
generator the tests use:
```sh
python scripts/make_synthetic_dataset.py --output SyntheticDataset --lights 10
```
This writes `SyntheticDataset/{lights,darks,flats,biases}/` under the repo
root — point a workspace's `source_path` at it like any other dataset folder.

### Frontend

```sh
cd astro-stacks
tsc --noEmit      # typecheck
pnpm build        # typecheck + production build
pnpm dev          # run the UI in a browser against the live backend for manual testing
```

There's no frontend test suite yet — UI changes are verified manually against
the running backend (`pnpm dev` + `uvicorn api:app --reload`).

## Common gotchas

- A workspace's `source_path` is referenced in place, not copied — if you
  move or delete that folder, the workspace's frame counts and future runs
  will fail (existing saved versions are unaffected, since those live under
  `astro-stacks/workspaces/<id>/`).
- The pipeline needs at least 2 light frames to stack. `apply_dark` /
  `apply_flat` are independent toggles — each is skipped gracefully if the
  corresponding `darks/`/`flats/` folder is missing or empty, regardless of
  the other's setting.
- The saved master (`astro-stacks/workspaces/<id>/master_linear.npy`) is
  linear, unstretched data — stretching happens only in `/preview` and when
  saving a version, so re-running the pipeline is only needed when the
  underlying frames or stacking params change, not when you're just
  adjusting the stretch.
- Saving a version requires a master to already be loaded
  (`POST /workspaces/{id}/load_master`) — the frontend does this
  automatically after a run completes or when opening a workspace that
  already has a stacked master.
