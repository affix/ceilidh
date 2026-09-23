#!/usr/bin/env bash
#
# Build a Ceilidh .deb. The package carries its own virtualenv, so the target
# machine needs nothing but glibc and a sound card.
#
#   tools/build-deb.sh                  # arm64, for a Raspberry Pi 4 on 64 bit Pi OS
#   tools/build-deb.sh --arch amd64
#   tools/build-deb.sh --native         # already on Debian, skip Docker
#
set -euo pipefail

ARCH="arm64"
OUTPUT="dist"
IMAGE="debian:bookworm-slim"
MAINTAINER='Keiran "Affix" Smith <opensource@keiran.scot>'
NATIVE=0

usage() {
    sed -n '2,12p' "$0" | sed 's/^# \{0,1\}//'
    cat <<'EOF'

Options:
  --arch ARCH         arm64 (default), amd64 or armhf
  --output DIR        where to drop the .deb (default dist)
  --image IMAGE       build image (default debian:bookworm-slim)
  --maintainer NAME   Maintainer field
  --native            build here instead of in Docker (needs Debian + dpkg-deb)
EOF
}

while [ $# -gt 0 ]; do
    case "$1" in
        --arch) ARCH="$2"; shift 2 ;;
        --output) OUTPUT="$2"; shift 2 ;;
        --image) IMAGE="$2"; shift 2 ;;
        --maintainer) MAINTAINER="$2"; shift 2 ;;
        --native) NATIVE=1; shift ;;
        -h|--help) usage; exit 0 ;;
        *) echo "unknown option: $1" >&2; usage >&2; exit 2 ;;
    esac
done

case "$ARCH" in
    arm64) PLATFORM="linux/arm64" ;;
    amd64) PLATFORM="linux/amd64" ;;
    armhf) PLATFORM="linux/arm/v7" ;;
    *) echo "unsupported arch: $ARCH (arm64, amd64, armhf)" >&2; exit 2 ;;
esac

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="$(sed -n 's/^version = "\(.*\)"/\1/p' "$REPO/pyproject.toml" | head -1)"
[ -n "$VERSION" ] || { echo "could not read the version out of pyproject.toml" >&2; exit 1; }
mkdir -p "$REPO/$OUTPUT"

INNER=$(cat <<'INNER_EOF'
set -euo pipefail
VERSION="$1"; ARCH="$2"; MAINTAINER="$3"
SRC="${SRC:-/src}"; OUT="${OUT:-/out}"
export DEBIAN_FRONTEND=noninteractive

echo ">> installing build tools"
apt-get update -qq
apt-get install -y -qq --no-install-recommends \
    python3 python3-venv python3-pip ca-certificates >/dev/null

echo ">> copying the source"
rm -rf /build /stage /opt/ceilidh
mkdir -p /build
cp -a "$SRC"/ceilidh "$SRC"/tools "$SRC"/packaging "$SRC"/pyproject.toml "$SRC"/README.md /build/

echo ">> building the virtualenv"
python3 -m venv /opt/ceilidh/venv
/opt/ceilidh/venv/bin/pip install -q --no-cache-dir --upgrade pip >/dev/null
/opt/ceilidh/venv/bin/pip install -q --no-cache-dir /build

echo ">> checking it imports"
/opt/ceilidh/venv/bin/python3 -c \
    "import pygame, ceilidh; print('   pygame-ce', pygame.version.ver, '| ceilidh', ceilidh.__version__)"

echo ">> slimming"
/opt/ceilidh/venv/bin/pip uninstall -y -q pip >/dev/null 2>&1 || true
find /opt/ceilidh/venv -name '__pycache__' -type d -prune -exec rm -rf {} + 2>/dev/null || true
find /opt/ceilidh/venv -name '*.pyc' -delete 2>/dev/null || true
rm -rf /opt/ceilidh/venv/share \
       /opt/ceilidh/venv/lib/python*/site-packages/pip* \
       /opt/ceilidh/venv/lib/python*/site-packages/setuptools* \
       /opt/ceilidh/venv/lib/python*/site-packages/_distutils_hack \
       /opt/ceilidh/venv/lib/python*/site-packages/distutils-precedence.pth 2>/dev/null || true

echo ">> staging the package"
mkdir -p /stage/DEBIAN /stage/opt/ceilidh /stage/usr/bin /stage/lib/systemd/system \
         /stage/usr/share/applications /stage/usr/share/doc/ceilidh /stage/var/lib/ceilidh/songs
cp -a /opt/ceilidh/venv /stage/opt/ceilidh/venv
cp -a /build/tools /stage/opt/ceilidh/tools
rm -f /stage/opt/ceilidh/tools/build-deb.sh
cp /build/README.md /stage/usr/share/doc/ceilidh/README.md
cp /build/packaging/ceilidh-kiosk.service /stage/lib/systemd/system/
cp /build/packaging/ceilidh.desktop /stage/usr/share/applications/

cat > /stage/usr/bin/ceilidh <<'EOF'
#!/bin/sh
exec /opt/ceilidh/venv/bin/ceilidh "$@"
EOF
cat > /stage/usr/bin/ceilidh-ziv <<'EOF'
#!/bin/sh
exec /opt/ceilidh/venv/bin/python3 /opt/ceilidh/tools/ziv.py "$@"
EOF
chmod 755 /stage/usr/bin/ceilidh /stage/usr/bin/ceilidh-ziv

SIZE="$(du -s --block-size=1024 /stage | cut -f1)"
sed -e "s|@VERSION@|${VERSION}|" -e "s|@ARCH@|${ARCH}|" \
    -e "s|@MAINTAINER@|${MAINTAINER}|" -e "s|@SIZE@|${SIZE}|" \
    /build/packaging/control.in > /stage/DEBIAN/control
install -m 755 /build/packaging/postinst /build/packaging/prerm /build/packaging/postrm /stage/DEBIAN/

echo ">> building the deb"
dpkg-deb --build --root-owner-group /stage "$OUT/ceilidh_${VERSION}_${ARCH}.deb" >/dev/null
dpkg-deb --info "$OUT/ceilidh_${VERSION}_${ARCH}.deb" | sed 's/^/   /'
echo ">> done: ceilidh_${VERSION}_${ARCH}.deb"
INNER_EOF
)

if [ "$NATIVE" -eq 1 ]; then
    command -v dpkg-deb >/dev/null || { echo "dpkg-deb is not here, drop --native" >&2; exit 1; }
    [ "$(id -u)" -eq 0 ] || echo "note: a native build writes to /opt, so it wants root"
    SRC="$REPO" OUT="$REPO/$OUTPUT" bash -c "$INNER" -- "$VERSION" "$ARCH" "$MAINTAINER"
    exit 0
fi

command -v docker >/dev/null || { echo "docker is not installed" >&2; exit 1; }
if [ "$ARCH" = "armhf" ]; then
    echo "note: armhf runs under emulation on an arm64 or amd64 host, so this will be slow"
fi

echo "docker run --rm -i --platform $PLATFORM \\"
echo "  -v \"$REPO:/src:ro\" -v \"$REPO/$OUTPUT:/out\" \\"
echo "  $IMAGE bash -s -- $VERSION $ARCH \"$MAINTAINER\""
echo

printf '%s' "$INNER" | docker run --rm -i --platform "$PLATFORM" \
    -v "$REPO:/src:ro" \
    -v "$REPO/$OUTPUT:/out" \
    "$IMAGE" bash -s -- "$VERSION" "$ARCH" "$MAINTAINER"

echo
ls -lh "$REPO/$OUTPUT"/ceilidh_"${VERSION}"_"${ARCH}".deb
