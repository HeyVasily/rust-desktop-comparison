
#include <dlfcn.h>
#include <spawn.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>

extern char **environ;

int main(int argc, char **argv) {
    if (argc < 2) return 64;
    int (*disclaim)(posix_spawnattr_t, int) =
        dlsym(RTLD_DEFAULT, "responsibility_spawnattrs_setdisclaim");
    if (!disclaim) {
        fputs("macOS responsibility spawn API unavailable\n", stderr);
        return 69;
    }
    posix_spawnattr_t attributes;
    int error = posix_spawnattr_init(&attributes);
    if (error) {
        fprintf(stderr, "posix_spawnattr_init: %s\n", strerror(error));
        return 71;
    }
    error = posix_spawnattr_setflags(&attributes, POSIX_SPAWN_SETEXEC);
    if (!error) error = disclaim(&attributes, 1);
    pid_t pid = 0;
    if (!error) error = posix_spawn(&pid, argv[1], NULL, &attributes, argv + 1, environ);
    posix_spawnattr_destroy(&attributes);
    fprintf(stderr, "macOS responsibility launch: %s\n", strerror(error));
    return 71;
}
