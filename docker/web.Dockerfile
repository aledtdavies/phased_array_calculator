# The browser version as a self-contained web server, for a work network (plan: web app).
#
#   docker build -t pac-web -f docker/web.Dockerfile --build-arg PAC_BUILD="$(git log -1 --format='%h %cs')" .
#   (PAC_BUILD: the commit the page shows under its status line; the image has no .git of its own)
#   docker run -d --restart unless-stopped -p 8080:80 pac-web     # then browse to http://<server>:8080/
#
# Stage 1 builds the static site with Pyodide, Plotly and the DXF reader copied in
# (tools/build_web.py --offline): the
# build needs internet access once; the running container and the browsers using it do not.
# Stage 2 serves it with nginx. The calculation runs in each user's browser; the server only
# hands out files, and nothing a user enters is sent to it.
FROM python:3.12-slim-bookworm AS build
WORKDIR /src
COPY web web
COPY python python
COPY tools/build_web.py tools/build_web.py
COPY THIRD_PARTY_NOTICES.md .
COPY docs/beam_field_model.html docs/beam_field_model.html
ARG PAC_BUILD=""
RUN PAC_BUILD="$PAC_BUILD" python tools/build_web.py /site --offline

FROM nginx:1.27-alpine
COPY docker/web-nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /site /usr/share/nginx/html
