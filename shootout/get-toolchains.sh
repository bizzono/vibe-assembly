#!/bin/bash
# Fetch user-local copies of the compilers and runtimes the shootout compares against,
# into .toolchains/ at the repository root. Nothing is installed system-wide and nothing
# outside this repository is modified; delete .toolchains/ to undo.
#
# Only needed to reproduce the published table. `shootout.py` uses whatever it finds on
# PATH and skips languages that are missing.
#
# Apple Silicon macOS only. Usage: shootout/get-toolchains.sh [rust zig java python ruby]
# (no arguments: rust zig java python; ruby is built from source and must be named)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TC="$ROOT/.toolchains"
mkdir -p "$TC/bin" "$TC/dl"
[ "$(uname -sm)" = "Darwin arm64" ] || { echo "this script supports Apple Silicon macOS only" >&2; exit 1; }

want() { [ $# -eq 0 ] && return 0; local x; for x in "${WANT[@]}"; do [ "$x" = "$1" ] && return 0; done; return 1; }
WANT=("$@"); [ ${#WANT[@]} -eq 0 ] && WANT=(rust zig java python)

fetch() { # url dest
  [ -s "$2" ] || curl --proto '=https' --tlsv1.2 -fsSL --retry 3 -o "$2" "$1"
}
link() { # absolute-binary name
  ln -sf "$1" "$TC/bin/$2"
}

if want rust && [ ! -x "$TC/cargo/bin/rustc" ]; then
  echo "== rust (rustup, minimal profile)"
  fetch https://sh.rustup.rs "$TC/dl/rustup-init.sh"
  RUSTUP_HOME="$TC/rustup" CARGO_HOME="$TC/cargo" sh "$TC/dl/rustup-init.sh" -y --profile minimal \
      --default-toolchain stable --no-modify-path >/dev/null
fi
if [ -x "$TC/cargo/bin/rustc" ]; then
  # rustup's shims need to know where the toolchain lives
  printf '#!/bin/sh\nRUSTUP_HOME="%s" CARGO_HOME="%s" exec "%s" "$@"\n' "$TC/rustup" "$TC/cargo" "$TC/cargo/bin/rustc" > "$TC/bin/rustc"
  chmod +x "$TC/bin/rustc"
fi

if want zig && [ ! -x "$TC/zig/zig" ]; then
  echo "== zig (latest stable from ziglang.org)"
  fetch https://ziglang.org/download/index.json "$TC/dl/zig-index.json"
  read -r ZURL ZSHA < <(python3 - "$TC/dl/zig-index.json" <<'PY'
import json, sys
idx = json.load(open(sys.argv[1]))
def key(v): return tuple(int(x) for x in v.split("."))
stable = max((v for v in idx if v[0].isdigit() and "-" not in v), key=key)
e = idx[stable]["aarch64-macos"]
print(e["tarball"], e["shasum"])
PY
)
  fetch "$ZURL" "$TC/dl/zig.tar.xz"
  echo "$ZSHA  $TC/dl/zig.tar.xz" | shasum -a 256 -c - >/dev/null
  rm -rf "$TC/zig" && mkdir -p "$TC/zig" && tar -xJf "$TC/dl/zig.tar.xz" -C "$TC/zig" --strip-components 1
fi
[ -x "$TC/zig/zig" ] && link "$TC/zig/zig" zig

if want java && [ ! -x "$TC/java/Contents/Home/bin/java" ]; then
  echo "== java (Eclipse Temurin JDK 25)"
  fetch "https://api.adoptium.net/v3/binary/latest/25/ga/mac/aarch64/jdk/hotspot/normal/eclipse" "$TC/dl/jdk.tar.gz"
  fetch "https://api.adoptium.net/v3/assets/latest/25/hotspot?architecture=aarch64&image_type=jdk&os=mac&vendor=eclipse" "$TC/dl/jdk.json"
  JSHA=$(python3 -c "import json,sys; print(json.load(open(sys.argv[1]))[0]['binary']['package']['checksum'])" "$TC/dl/jdk.json")
  echo "$JSHA  $TC/dl/jdk.tar.gz" | shasum -a 256 -c - >/dev/null
  rm -rf "$TC/java" && mkdir -p "$TC/java" && tar -xzf "$TC/dl/jdk.tar.gz" -C "$TC/java" --strip-components 1
fi
if [ -x "$TC/java/Contents/Home/bin/java" ]; then
  link "$TC/java/Contents/Home/bin/java" java
  link "$TC/java/Contents/Home/bin/javac" javac
fi

if want python && [ ! -x "$TC/python/bin/python3" ]; then
  echo "== python (CPython, python-build-standalone)"
  fetch https://api.github.com/repos/astral-sh/python-build-standalone/releases/latest "$TC/dl/pbs.json"
  read -r PURL PSHA < <(python3 - "$TC/dl/pbs.json" <<'PY'
import json, re, sys
rel = json.load(open(sys.argv[1]))
best = None
for a in rel["assets"]:
    m = re.match(r"cpython-(3\.(\d+)\.(\d+))\+\d+-aarch64-apple-darwin-install_only_stripped\.tar\.gz$", a["name"])
    if m:
        k = (int(m.group(2)), int(m.group(3)))
        if best is None or k > best[0]:
            best = (k, a["browser_download_url"], (a.get("digest") or "").replace("sha256:", ""))
print(best[1], best[2] or "-")
PY
)
  fetch "$PURL" "$TC/dl/python.tar.gz"
  [ "$PSHA" = "-" ] || echo "$PSHA  $TC/dl/python.tar.gz" | shasum -a 256 -c - >/dev/null
  rm -rf "$TC/python" && mkdir -p "$TC/python" && tar -xzf "$TC/dl/python.tar.gz" -C "$TC/python" --strip-components 1
fi
[ -x "$TC/python/bin/python3" ] && link "$TC/python/bin/python3" python3

# Ruby has no official macOS binaries, so it is built from the release tarball (a few
# minutes). Not in the default set: ask for it by name.
if want ruby && [ "${1:-}" != "" ] && [ ! -x "$TC/ruby/bin/ruby" ]; then
  echo "== ruby (built from source, with YJIT if rustc is available)"
  fetch https://cache.ruby-lang.org/pub/ruby/index.txt "$TC/dl/ruby-index.txt"
  read -r RURL RSHA < <(python3 - "$TC/dl/ruby-index.txt" <<'PY'
import re, sys
best = None
for line in open(sys.argv[1]):
    parts = line.split()
    if len(parts) >= 4 and re.fullmatch(r"ruby-(\d+)\.(\d+)\.(\d+)", parts[0]) and parts[1].endswith(".tar.gz"):
        k = tuple(int(x) for x in parts[0][5:].split("."))
        if best is None or k > best[0]:
            best = (k, parts[1], parts[3])
print(best[1], best[2])
PY
)
  fetch "$RURL" "$TC/dl/ruby.tar.gz"
  echo "$RSHA  $TC/dl/ruby.tar.gz" | shasum -a 256 -c - >/dev/null
  rm -rf "$TC/ruby-src" && mkdir -p "$TC/ruby-src" && tar -xzf "$TC/dl/ruby.tar.gz" -C "$TC/ruby-src" --strip-components 1
  ( cd "$TC/ruby-src"
    YJIT=--disable-yjit; [ -x "$TC/bin/rustc" ] && YJIT=--enable-yjit
    PATH="$TC/bin:$PATH" ./configure --prefix="$TC/ruby" --disable-install-doc --disable-install-rdoc $YJIT \
        --with-out-ext=openssl,psych,readline,fiddle,zlib,dbm,gdbm,win32,win32ole >/dev/null
    PATH="$TC/bin:$PATH" make -j4 >/dev/null 2>"$TC/dl/ruby-build.log"
    make install >/dev/null 2>>"$TC/dl/ruby-build.log" )
  rm -rf "$TC/ruby-src"
fi
[ -x "$TC/ruby/bin/ruby" ] && link "$TC/ruby/bin/ruby" ruby

echo
echo "toolchains in $TC/bin:"
for t in rustc zig java javac python3 ruby; do
  v=--version; [ "$t" = zig ] && v=version
  if [ -x "$TC/bin/$t" ]; then printf '  %-8s %s\n' "$t" "$("$TC/bin/$t" $v 2>&1 | head -1)"; fi
done
du -sh "$TC" | awk '{print "  total size: " $1}'
