# The browser version: publishing, sharing and hosting

**Address:** <https://aledtdavies.github.io/phased_array_calculator/>
(help for users: [`help.html`](https://aledtdavies.github.io/phased_array_calculator/help.html)).

The browser version runs the calculator's own Python (`python/`) in the user's browser through
[Pyodide](https://pyodide.org). Nothing is installed, and nothing a user enters leaves their browser.
The plan, the measurements and the comparison of hosting options are in
[`plans/PLAN-2026-11-web-app.md`](plans/PLAN-2026-11-web-app.md).

## For colleagues

Send them the address. They need a current browser (Edge, Chrome, Safari or Firefox; phones and
tablets work too) and nothing else; the first visit takes about 20 s to start. The Help link on the
page covers using it and what to do if it does not start. It has the desktop window's inputs, tabs
(the 3D view included) and files. How the two versions are kept the same:
`docs/plans/PLAN-2026-11-web-desktop-parity.md`.

## Publishing (GitHub Pages)

- **Automatic:** every merge to `main` runs the `pages` workflow (`.github/workflows/pages.yml`).
  It builds the site with `tools/build_web.py site --offline`, with Pyodide copied in, so users'
  browsers load everything from `github.io` and nothing from other sites. It then publishes the
  site. The new version is live about two minutes after the merge.
- **On demand:** Actions > **pages** > **Run workflow** (branch `main`).
- **Check it:** Actions > pages shows each run, with the address in its deploy step. Open the
  address and wait for *Ready*.
- **Roll back:** revert the faulty change on `main`, as a pull request merged like any other. The
  merge republishes the earlier state within about two minutes. The site can only be published
  from `main`: GitHub's `github-pages` environment accepts deployments from the default branch only.
- **Take it offline:** Settings > Pages > **Unpublish site**. Settings > Pages > Source must stay
  "GitHub Actions" for the workflow to publish.
- **Cost and visibility:** free because the repository is public. The site is public too: anyone
  with the address can use it. Users' inputs stay in their own browsers.

## Hosting on the work network instead

Use this if the site must stay internal, or if the work network blocks `github.io`. Either way
the server only serves files; the calculation runs in each user's browser. The server needs no
internet access once the site is built.

### Option A: a ready-made site folder, for any web server IT already runs

1. Download the site: Actions > **headless** (any recent run on `main`) > Artifacts >
   **pac-web-site**. GitHub wraps every artefact in its own zip, so the download is
   `pac-web-site.zip` containing `pac-web-site.zip` (about 23 MB). Unzip the download once to get
   the inner zip. Alternatively, build the site folder on any machine with Python and internet
   access: `python tools/build_web.py site --offline`.
2. Unzip the **inner** `pac-web-site.zip` into a folder the web server publishes, for example
   `C:\inetpub\wwwroot\pac\` on IIS. `index.html` must end up directly in that folder.
3. The server must send:

   | Extension | Content type |
   |---|---|
   | `.mjs` | `text/javascript` |
   | `.wasm` | `application/wasm` |
   | `.py` | `text/plain` |
   | `.whl` | `application/zip` |

   - **IIS:** the included `web.config` sets these four types, so nothing needs configuring. If
     the server forbids `web.config` overrides, add the four types under the site's MIME Types.
   - **nginx or Apache:** recent versions know `.wasm`; add the others in their MIME settings.
4. Browse to the folder's address, for example `http://<server>/pac/`. The page must be served
   over http or https; opening `index.html` from a shared drive does not work.

### Option B: Docker

On the server, with the repository checked out (the build needs internet access once):

```
docker build -t pac-web -f docker/web.Dockerfile --build-arg PAC_BUILD="$(git log -1 --format='%h %cs')" .
docker run -d --name pac-web --restart unless-stopped -p 8080:80 pac-web
```

`PAC_BUILD` is the commit the page shows under its status line, so users can tell which version
they have. Without it the page shows no build.

Then browse to `http://<server>:8080/`. The image is nginx with the self-contained site, and its
content types are set and checked in CI (the `web` job of `headless.yml`). To update, pull the
repository and run both commands again (stop and remove the old container first:
`docker rm -f pac-web`).

## What to check on a work laptop (once)

1. The page reaches *Ready*. If it stays on *Loading…*, the network probably blocks `github.io`:
   use the work server instead.
2. An error naming WebAssembly means the browser's policy blocks WebAssembly. That is an IT
   setting; no hosting choice avoids it.
3. Note the timings shown at the bottom of the page. On the dev laptop it was ready in 18–19 s,
   and a 2D beam field took 2–5 s.

## Changing the browser version

- The page is `web/` (`index.html`, `help.html`, `app.js`, `worker.js`). The Python layer is
  `web/pac_web.py`, and the calculation itself is `python/`, shared with the desktop window.
- **To try a change locally:** `python tools/build_web.py site`, then
  `cd site && python -m http.server 8000` and open <http://localhost:8000/>.
- `python/test_web.py` checks that the browser's Python layer matches the desktop calculation.
  CI builds the work-server image and checks what a browser fetches from it.
- **Security:** the worker runs code only from the site itself or the pinned Pyodide release on
  jsDelivr. The page's address cannot change where code comes from.
