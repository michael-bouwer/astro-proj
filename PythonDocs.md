# Getting started with the Python Dev.

To start working in in the Python environment, run
```py
.\venv\Scripts\activate
```

## Installing and Loading dependencies

To install the current dependencies according to the last recorded versions:
```py
pip install -r requirements.txt
```

To save changes to versions or new packages:
```py
pip freeze > requirements.txt
```

## Starting the FastAPI Server
```py
uvicorn api:app --reload
```

## Stacking pipeline (`pipeline/`)

The stacking logic used to live in a single `test.py` script. It's now a
package so each stage can be reused, tested, and driven from the API:

- `raw_io.py` — loading raw/CR2 and image frames, saving/loading the linear master
- `calibration.py` — bias/dark/flat master frames and light-frame calibration
- `alignment.py` — astroalign-based star registration (ORB+RANSAC fallback)
- `stacking.py` — disk-backed, sigma-clipped stacking
- `color.py` — background neutralization + star color calibration (linear space)
- `stretch.py` — MTF / asinh display stretches (applied on demand, never baked into the saved master)
- `halos.py` — star halo/ring artifact cleanup
- `orchestrator.py` — runs the full pipeline for a dataset directory and saves `master_linear.npy`

A dataset directory needs a `lights/` subfolder, and optionally `darks/`,
`flats/`, `biases/` for calibration.

### API endpoints

- `GET /datasets` — list dataset folders under the project root with frame counts
- `POST /pipeline/run` — `{dataset, sigma, use_calibration}`, runs the pipeline as a background job, returns `job_id`
- `GET /pipeline/status/{job_id}` — poll job progress/result
- `POST /load_master?dataset=...` — loads a dataset's `master_linear.npy` into memory for preview
- `GET /preview?method=mtf|asinh&midtone=0.25&scale=1000` — JPEG preview with a live stretch
- `POST /export` — `{dataset, method, midtone, scale, fix_halos}`, writes a stretched 16-bit `export.tiff`