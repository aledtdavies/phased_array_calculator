# Headless image of the Phased Array Focal Law Calculator (plan step 7): runs the test suite
# and renders the documentation screenshots without a GPU or a desktop.
#
#   docker build -t pac-headless -f docker/Dockerfile .
#   docker run --rm -v "$PWD/out:/out" pac-headless test      # test suite -> /out/junit.xml
#   docker run --rm -v "$PWD/out:/out" pac-headless images    # screenshots -> /out/images
#
# Display: Xvfb (a virtual X server) with Mesa's software OpenGL (llvmpipe), so Qt uses its
# native xcb platform and VTK its usual GLX path, exactly as on a desktop. Not for shipping the
# GUI to colleagues (see docs/plans/PLAN-2026-11-qt-vtk-migration.md, Docker).
FROM python:3.12-slim-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    QT_API=pyside6 \
    QT_QPA_PLATFORM=xcb \
    LIBGL_ALWAYS_SOFTWARE=1 \
    MPLBACKEND=Agg

# X server, Mesa software GL, the xcb libraries Qt's platform plugin loads, fonts.
RUN apt-get update && apt-get install -y --no-install-recommends \
        xvfb xauth \
        libgl1 libegl1 libglx-mesa0 libgl1-mesa-dri libglu1-mesa \
        libx11-6 libx11-xcb1 libxext6 libxrender1 libxi6 libsm6 libice6 libxt6 \
        libxkbcommon0 libxkbcommon-x11-0 libxcb1 libxcb-cursor0 libxcb-icccm4 libxcb-image0 \
        libxcb-keysyms1 libxcb-randr0 libxcb-render-util0 libxcb-shape0 libxcb-xinerama0 \
        libxcb-xkb1 libxcb-xfixes0 libxcb-shm0 libxcb-sync1 libxcb-glx0 \
        libfontconfig1 libfreetype6 libdbus-1-3 fonts-dejavu-core \
        libglib2.0-0 libopengl0 libegl-mesa0 libxcomposite1 libxdamage1 libxrandr2 libxtst6 libxcursor1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY python/requirements.txt python/requirements.txt
RUN pip install -r python/requirements.txt pytest

COPY . .
RUN chmod +x docker/entrypoint.sh

ENTRYPOINT ["/app/docker/entrypoint.sh"]
CMD ["test"]
