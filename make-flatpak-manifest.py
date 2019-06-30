#!/usr/bin/python3.7

# Copyright (C) 2019 Andrew Hamilton. All rights reserved.
# Licensed under the Artistic License 2.0.


import json
import os.path
import pathlib
import subprocess
import tempfile

import eris.tools


def get_package_sources(packages):
    output = subprocess.check_output(["apt-get", "source", "--print-uris"]
                                     + packages, text=True)
    seen = set()
    for line in output.splitlines():
        if line.startswith("'") and ".dsc" not in line:
            parts = line.split()
            package = parts[1].split("_")[0]
            url = parts[0][1:-1]
            sha256 = parts[3][-64:]
            if package not in seen:
                yield package, url, sha256
                seen.add(package)


def make_simple_module(package, url, sha256):
    return {"name": package,
            "sources": [{"type": "archive",
                         "url": url,
                         "sha256": sha256}]}


def get_file_sha256(path):
    return subprocess.check_output(["sha256sum", path], text=True).split()[0]


def get_url_sha256(url):
    with tempfile.TemporaryDirectory() as temp_dir:
        subprocess.check_output(["wget", "-O", "file", url], cwd=temp_dir,
                                stderr=subprocess.STDOUT)
        return get_file_sha256(os.path.join(temp_dir, "file"))


def get_haskell_deps(package):
    subprocess.check_output(["cabal", "update"])
    with tempfile.TemporaryDirectory() as temp_dir:
        subprocess.check_output(["cabal", "sandbox", "init"], cwd=temp_dir)
        lines = subprocess.check_output([
            "cabal", "install", "--allow-boot-library-installs",
            "--reinstall", "--dry-run", package],
                cwd=temp_dir, text=True).splitlines()[2:]
    return [line.split()[0] for line in lines if not line.startswith("Use")]


def make_haskell_module(package, deps):
    commands = []
    sources = []
    for dep in deps:
        package_url = f"http://hackage.haskell.org/package/{dep}"
        url = package_url + f"/{dep}.tar.gz"
        sources.append({"type": "archive", "url": url,
                        "sha256": get_url_sha256(url), "dest": dep})
        revision = 1
        try:
            while True:
                revision_url = package_url + f"/revision/{revision}.cabal"
                sha256 = get_url_sha256(revision_url)
                last_url = revision_url
                revision += 1
        except subprocess.CalledProcessError:
            revision -= 1
        if revision > 0:
            revision_path = dep.rsplit("-", maxsplit=1)[0] + ".cabal"
            sources.append({"type": "file", "url": last_url, "sha256": sha256,
                            "dest": dep, "dest-filename": revision_path})
        commands.extend([
            f"cd {dep}; ghc -threaded --make Setup",
            f"cd {dep}; ./Setup configure --disable-optimization --prefix=/app",
            f"cd {dep}; ./Setup build",
            f"cd {dep}; ./Setup install"])
    for dep in reversed(deps):
        commands.append(f"cd {dep}; ./Setup unregister")
    return {"name": f"haskell-{package}", "buildsystem": "simple",
            "build-commands": commands, "builddir": True, "sources": sources,
            "cleanup": ["/lib/x86_64-linux-ghc-*"]}


def haskell_modules(dep):
    modules = []
    for package, url, sha256 in get_package_sources(["ghc"]):
        modules.append(make_simple_module(package, url, sha256))
    modules = [patch_module(module, patches) for module in modules]    
    modules.append(make_haskell_module(dep, get_haskell_deps(dep)))
    return modules


def python_modules(package):
    python_version = "python3.7"
    with tempfile.TemporaryDirectory() as temp_dir:
        output = subprocess.check_output(
            [python_version, "-m", "pip", "download", "--dest", temp_dir,
             package], text=True)
        sources = []
        for line in output.splitlines():
            if (line.startswith("  Downloading") or
                line.startswith("  Using cached")):
                url = line.split()[-1]
                archive_path = os.path.join(temp_dir, os.path.basename(url))
                sources.append((url, get_file_sha256(archive_path)))
    assert sources != [], ("No python modules found for:", package)
    return [{"name": python_version + "-" + package,
             "buildsystem": "simple",
             "build-commands": [
                 python_version + " -m pip install --no-index"
                 " --find-links="file://${PWD}" --prefix=/app " + package
             ],
             "sources": [{"type": "file", "url": url, "sha256": sha256}
                         for url, sha256 in sorted(sources)]}]


def go_repo_source(repo_path):
    current_commit = subprocess.check_output(["git", "rev-parse", "HEAD"],
                                             cwd=repo_path, text=True).strip()
    remote_url = subprocess.check_output(["git", "remote", "get-url", "origin"],
                                         cwd=repo_path, text=True).strip()
    dest_path = repo_path[repo_path.rfind("src/"):]
    return {"type": "git", "url": remote_url, "commit": current_commit,
            "dest": dest_path}


def go_repo_paths(build_dir):
    src_dir = build_dir / "src"
    go_repo_paths = []
    domains = src_dir.iterdir()
    for domain in domains:
        domain_users = domain.iterdir()
        for user in domain_users:
            user_repos = user.iterdir()
            go_repo_paths += list(user_repos)
    return go_repo_paths


def go_modules(package_url):
    with tempfile.TemporaryDirectory() as temp_dir:
        new_env = os.environ.copy()
        new_env.update({"GOPATH": temp_dir})
        subprocess.run(["go", "get", "-d", package_url], cwd=temp_dir,
                       env=new_env, check=True)
        sources = [go_repo_source(str(repo_path))
                   for repo_path in go_repo_paths(pathlib.Path(temp_dir))]
    return [{"name": os.path.basename(package_url),
             "buildsystem": "simple",
             "build-options": {"env": {"GOBIN": "/app/bin"}},
             "build-commands":
             [". /usr/lib/sdk/golang/enable.sh; "
              f"GOPATH=$PWD go install {package_url}"],
             "sources": sources}]


def git_repo_latest_commit(repo_url):
    with tempfile.TemporaryDirectory() as temp_dir:
        subprocess.run(["git", "clone", "--bare", "--depth=1",
                        repo_url, temp_dir], check=True, capture_output=True)
        with open(os.path.join(temp_dir, "shallow")) as shallow_file:
            return shallow_file.read().strip()


def git_modules(package_url):
    remote_url = "https://" + package_url
    modules = [{"name": os.path.basename(package_url),
                "sources": [{"type": "git", "url": remote_url,
                             "commit": git_repo_latest_commit(remote_url)}]}]
    return [patch_module(module, patches) for module in modules]


patches = {
    "cppcheck": {"buildsystem": "cmake"},

    # For genisoimage.
    "cdrkit": {"buildsystem": "simple",
               "build-commands": [
                   "cmake .",
                   "make -j4 isoinfo",
                   "install -D -t /app/bin genisoimage/isoinfo"]},

    "db5.3": {"buildsystem": "simple",
              "build-commands": [
                  "cd build_unix && ../dist/configure"
                  " --prefix=/app && make -j4 && make install"]},

    "dpkg": {"buildsystem": "simple",
             "build-commands": [
                 "./configure --disable-dselect --disable-start-stop-daemon "
                 "--disable-update-alternatives --prefix=/app",
                 "make install"]},

    "ghc": {"buildsystem": "simple",
            "build-commands": [
                "mkdir -p /app/lib",
                "ln -s /usr/lib/x86_64-linux-gnu/libtinfo.so.6 /app/lib/libtinfo.so.5",
                "./configure --prefix=/app",
                "make install"],
            "sources": [{
                "type": "archive",
                "url": "https://downloads.haskell.org/~ghc/8.6.5/"
                       "ghc-8.6.5-x86_64-deb9-linux.tar.xz",
                "sha256": "bc75f5601a9f41d58b2ba161b9e28f"
                          "ad52143a7229060f1e084168d9b2e914df"}],
            "cleanup": ["/lib/ghc-*", "/lib/libtinfo*", "/app/bin/*ghc*",
                        "/app/bin/aeson-pretty", "/app/bin/hpc",
                        "/app/bin/haddock*", "/app/bin/hsc2hs",
                        "/app/bin/runhaskell", "/app/bin/hp2ps"]},
    
    "html2text": {"buildsystem": "simple",
                  "build-commands": [
                      "./configure --prefix=/app",
                      "make -j4",
                      "install -D -t /app/bin html2text"]},

    "libzen": {"subdir": "Project/GNU/Library"},

    "libmediainfo": {"subdir": "Project/GNU/Library"},

    "lua": {"buildsystem": "simple",
            "build-commands": [
                r'sed -e "s/INSTALL_TOP= \/usr\/local/INSTALL_TOP= \/app/" '
                 'Makefile > new',
                "mv new Makefile",
                "make -j4 linux",
                "make install"]},

    "lua5.3": {"buildsystem": "simple",
               "build-commands": [
                   r'sed -e "s/INSTALL_TOP= \/usr\/local/INSTALL_TOP= \/app/" '
                    'Makefile > new',
                   "mv new Makefile",
                   "make -j4 linux",
                   "make install"]},

    "mediainfo": {"subdir": "Project/GNU/CLI"},

    "php7.2": {"buildsystem": "simple",
               "build-commands": [
                   "./configure --prefix=/app --disable-all --disable-cgi"
                              " --disable-phpdbg",
                   "make -j4",
                   "make install"]},

    "ruby2.5": {"cleanup": ["/share/ri", "/lib/libruby-static.a",
                            "/lib/ruby/*/rdoc",
                            "/lib/ruby/*/x86_64-linux/enc"]},

    "perl": {"buildsystem": "simple",
             "build-commands": [
                 "./Configure -des -Dprefix=/app",
                 "make -j4",
                 "make install"],
             "post-install": [
                 "chmod 755 -R /app/lib/perl5/5.28.0/x86_64-linux/auto"],
             "sources": [{
                 "type": "archive",
                 "url": "http://www.cpan.org/src/5.0/perl-5.28.0.tar.xz",
                 "sha256": "059b3cb69970d8c8c5964caced0335b4a"
                           "f34ac990c8e61f7e3f90cd1c2d11e49"}]},

    "p7zip": {"buildsystem": "simple",
              "build-commands": [
                  "make -f makefile",
                  "install -DT bin/7za /app/bin/7z"]},

    "wabt": {"buildsystem": "simple",
             "build-commands": [
                 "mkdir build && cd build && "
                 "cmake -DCMAKE_INSTALL_PREFIX=/app ..",
                 "cd build && make -j4 install"]
             },
    
    "rpm": {"config-opts": ["--without-lua"]},

    "tidy-html5": {"buildsystem": "simple",
                   "build-commands": [
                       "cmake ../.. -DCMAKE_INSTALL_PREFIX=/app",
                       "make -j4",
                       "make install"],
                   "subdir": "build/cmake"},

    "unrar-nonfree": {"buildsystem": "simple",
                      "build-commands": [
                          "make -j4",
                          "install -D -t /app/bin unrar"]}}


def patch_module(module, patches):
    patch = patches.get(module["name"], {})
    module.update(patch)
    return module


def make_manifest(modules, dep):
    module_name = os.path.basename(dep)
    manifest = {"app-id": "com.github.ahamilton." + module_name,
                "runtime": "org.freedesktop.Sdk",
                "runtime-version": "18.08",
                "sdk": "org.freedesktop.Sdk",
                "sdk-extensions": ["org.freedesktop.Sdk.Extension.golang"],
                "cleanup": ["/lib/debug", "/share/man", "/man", "/include",
                            "/share/doc", "/doc", "/docs"],
                "strip": True,
                "modules": modules}
    if module_name == "eris":
        manifest["command"] = "eris"
    return manifest


EXTRA_DEPS = {"rpm": ["db5.3"],
              "mediainfo": ["libzen", "libmediainfo"]}


def ubuntu_modules(dep):
    new_dist_deps = []
    if dep in EXTRA_DEPS:
        new_dist_deps.extend(EXTRA_DEPS[dep])
    new_dist_deps.append(dep)
    modules = []
    for new_dist_dep in new_dist_deps:
        for package, url, sha256 in get_package_sources([new_dist_dep]):
            modules.append(make_simple_module(package, url, sha256))
    assert modules != []
    return [patch_module(module, patches) for module in modules]    
    

def lua_modules(dep):
    modules = [make_simple_module(
        "lua", "https://www.lua.org/ftp/lua-5.3.5.tar.gz",
        "0c2eed3f960446e1a3e4b9a1ca2f3ff893b6ce41942cf54d5dd59ab4b3b058ac")]
    modules = [patch_module(module, patches) for module in modules]
    modules.extend(git_modules("github.com/luarocks/luarocks"))
    modules[-1]["cleanup"] = ["*"]
    with tempfile.TemporaryDirectory() as temp_dir:
        process = subprocess.run(
            ["luarocks", "--verbose", "--to", temp_dir, "install", dep],
            check=True, capture_output=True, text=True)
    sources = []
    for line in process.stdout.splitlines():
        if line.startswith("Installing "):
            url = line.split()[1]
            sources.append({"type": "file", "url": url,
                            "sha256": get_url_sha256(url)})
    commands = ["luarocks-admin make-manifest .",
                f"luarocks install --only-from=$PWD {dep}"]
    return modules + [{"name": dep, "buildsystem": "simple",
                       "build-commands": commands,
                       "sources": sources}]


def get_latest_commit():
    return subprocess.check_output(["git", "rev-parse", "HEAD"],
                                   text=True).strip()


def eris_modules():
    eris_url = "https://github.com/ahamilton/eris"
    modules = []
    for dep in ["docopt", "pyinotify", "pygments", "pillow", "toml"]:
        modules.extend(python_modules(dep))
    modules.append({"name": "eris",
                    "buildsystem": "simple",
                    "build-commands": [
                        "python3.7 -m pip install --no-index --prefix=/app .",
                        "cp -a tests test-all /app/bin"],
                    "sources": [{"type": "git", "url": eris_url,
                                 "commit": get_latest_commit()}]})
    return modules


def nodejs_modules():
    return [{"name": "nodejs",
             "cleanup": ["/include", "/share", "/lib/node_modules",],
             "sources": [
                 {"type": "archive",
                  "url": "https://nodejs.org/dist/v9.9.0/node-v9.9.0.tar.gz",
                  "sha256": "e774cf32bc7c1d61d2e654e67eaafd2"
                            "a13f22f176933706de60250db5b5eabda"}]}]


BUILD_FUNCS = {"ubuntu": ubuntu_modules, "pip": python_modules,
               "haskell": haskell_modules, "go": go_modules,
               "git": git_modules, "luarocks": lua_modules}


def get_build_func(dep):
    build_type, package = (dep.split("/", maxsplit=1) if "/" in dep
                           else ("ubuntu", dep))
    return BUILD_FUNCS[build_type], package


DEPS_IN_RUNTIME = {"g++", "clang-format", "tar", "file", "perl-doc", "gcc",
                   "binutils", "coreutils", "git", "unzip", "python",
                   "python3", "python-setuptools"}


def save_manifest(manifest, manifest_path):
    with open(manifest_path, "w") as manifest_file:
        json.dump(manifest, manifest_file, indent=2)


def make_combined_manifest(all_modules):
    unique_modules = []
    seen = set()
    for module in all_modules:
        if module["name"] in seen:
            continue
        else:
            unique_modules.append(module)
            seen.add(module["name"])
    return make_manifest(unique_modules, "eris")


SUBSTITUTIONS = {"shellcheck": "haskell/ShellCheck",
                 "pandoc": "haskell/pandoc"}


manifests_dir = os.path.join(os.getcwd(), "manifests-cache")
os.makedirs(manifests_dir, exist_ok=True)
deps = {SUBSTITUTIONS.get(dep, dep) for dep in eris.tools.dependencies()}
all_modules = []
for dep in sorted(deps - DEPS_IN_RUNTIME) + ["eris"]:
    build_func, package = get_build_func(dep)
    dep_name = os.path.basename(package)
    manifest_path = os.path.join(manifests_dir, dep_name+".json")
    print(f"Making manifest for {dep} …".ljust(70), end="", flush=True)
    if os.path.exists(manifest_path):
        print(" (cached)")
        with open(manifest_path) as json_file:
            modules = json.load(json_file)["modules"]
        all_modules.extend(modules)
        continue
    elif dep == "eris":
        modules = eris_modules()
    elif dep == "nodejs":
        modules = nodejs_modules()
    else:
        modules = build_func(package)
    print()
    all_modules.extend(modules)
    save_manifest(make_manifest(modules, dep), manifest_path)
eris_module = all_modules[-1]
eris_module["sources"][0]["commit"] = get_latest_commit()
manifest = make_combined_manifest(all_modules)
manifest_path = "com.github.ahamilton.eris.json"
print()
print(f"Saving manifest file: ./{manifest_path}")
save_manifest(manifest, manifest_path)
