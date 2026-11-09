#!/usr/bin/env bash
# Root-only setup inside a disposable Debian-family VM. Input repository is $1.
set -euo pipefail
repo=${1:?repository directory required}
cd "$repo"
mkdir -p out/gtk-memory-ab/build out/gtk-memory-ab/results
export DEBIAN_FRONTEND=noninteractive
apt-get update >out/gtk-memory-ab/build/packages.log 2>&1
apt-get install -y --no-install-recommends build-essential pkg-config libgtk-4-dev xvfb openbox labwc grim python3-psutil python3-pil python3-tk dbus-x11 at-spi2-core fonts-dejavu-core xauth >>out/gtk-memory-ab/build/packages.log 2>&1
chown -R dev:dev "$repo"
{
    cat /etc/os-release
    uname -srmo
    pkg-config --modversion gtk4
    cc --version
    dpkg-query -W libgtk-4-1 libgl1-mesa-dri libegl-mesa0 mesa-vulkan-drivers libllvm19 labwc openbox xvfb fonts-dejavu-core at-spi2-core || true
    printf 'logical_cpus='; nproc
    awk '/MemTotal:/{print}' /proc/meminfo
} >out/gtk-memory-ab/build/environment.txt
runuser -u dev -- bash -c 'cd "$1"; cc -O2 -Wall -Wextra examples/gtk-c/main.c -o out/gtk-memory-ab/gtk-control $(pkg-config --cflags --libs gtk4)' bash "$repo" >out/gtk-memory-ab/build/compile.log 2>&1
sha256sum examples/gtk-c/main.c tools/gtk_memory_probe.py tools/gtk_memory_guest.sh out/gtk-memory-ab/gtk-control >out/gtk-memory-ab/build/hashes.txt
runuser -u dev -- python3 -m unittest discover -s tools -p test_gtk_memory_probe.py -v >out/gtk-memory-ab/build/tests.log 2>&1
runuser -u dev -- timeout --signal=TERM --kill-after=15 1300 python3 tools/gtk_memory_probe.py --binary out/gtk-memory-ab/gtk-control --output out/gtk-memory-ab/results
