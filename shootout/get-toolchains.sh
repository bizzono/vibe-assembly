#!/bin/bash
# Fetch user-local copies of the compilers and runtimes the shootout compares against,
# into .toolchains/ at the repository root. Nothing is installed system-wide and nothing
# outside this repository is modified; delete .toolchains/ to undo.
#
# Only needed to reproduce the published table. `shootout.py` uses whatever it finds on
# PATH and skips languages that are missing.
#
# Apple Silicon macOS only. Usage: shootout/get-toolchains.sh [rust zig java python ...]
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

echo
echo "toolchains in $TC/bin:"
for t in rustc zig java javac python3; do
  v=--version; [ "$t" = zig ] && v=version
  if [ -x "$TC/bin/$t" ]; then printf '  %-8s %s\n' "$t" "$("$TC/bin/$t" $v 2>&1 | head -1)"; fi
done
du -sh "$TC" | awk '{print "  total size: " $1}'
