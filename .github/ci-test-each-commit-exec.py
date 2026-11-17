#!/usr/bin/env python3
# Copyright (c) The Bitcoin Core developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or https://opensource.org/license/mit/.

import subprocess
import sys
import shlex


def run(cmd, **kwargs):
    print("+ " + shlex.join(cmd), flush=True)
    kwargs.setdefault("check", True)
    try:
        return subprocess.run(cmd, **kwargs)
    except Exception as e:
        sys.exit(str(e))


def cmake_werror_dev_flag():
    """Return -Werror=author on CMake >= 4.4, else -Werror=dev.

    -Werror=dev is deprecated in CMake 4.4+. -Werror=author is ignored
    (not treated as an error) on older CMake, so a plain swap would
    weaken the check below 4.4.
    """
    output = run(["cmake", "--version"], capture_output=True, text=True).stdout
    major = minor = 0
    for line in output.splitlines():
        parts = line.split()
        if len(parts) >= 3 and parts[0].lower() == "cmake" and parts[1].lower() == "version":
            nums = parts[2].split(".")
            major = int(nums[0]) if nums and nums[0].isdigit() else 0
            minor = int(nums[1]) if len(nums) > 1 and nums[1].isdigit() else 0
            break
    if (major, minor) >= (4, 4):
        return "-Werror=author"
    return "-Werror=dev"


def main():
    print("Running tests on commit ...")
    run(["git", "log", "-1"])

    num_procs = int(run(["nproc"], stdout=subprocess.PIPE).stdout)
    build_dir = "ci_build"

    run([
        "cmake",
        "-B",
        build_dir,
        cmake_werror_dev_flag(),
        # Use clang++, because it is a bit faster and uses less memory than g++
        "-DCMAKE_C_COMPILER=clang",
        "-DCMAKE_CXX_COMPILER=clang++",
        # Use mold, because it is faster than the default linker
        "-DCMAKE_EXE_LINKER_FLAGS=-fuse-ld=mold",
        # Use Debug build type for more debug checks, but enable optimizations
        "-DAPPEND_CXXFLAGS='-O3 -g2'",
        "-DAPPEND_CFLAGS='-O3 -g2'",
        "-DCMAKE_BUILD_TYPE=Debug",
        "-DCMAKE_COMPILE_WARNING_AS_ERROR=ON",
        "--preset=dev-mode",
        # Tolerate unused (member) functions in intermediate commits in a pull request
        "-DCMAKE_CXX_FLAGS=-Wno-error=unused-member-function -Wno-error=unused-function",
    ])

    if run(["cmake", "--build", build_dir, "-j", str(num_procs)], check=False).returncode != 0:
        print("Build failure. Verbose build follows.")
        run(["cmake", "--build", build_dir, "-j1", "--verbose"])

    run([
        "ctest",
        "--output-on-failure",
        "--stop-on-failure",
        "--test-dir",
        build_dir,
        "-j",
        str(num_procs),
    ])
    run([
        sys.executable,
        f"./{build_dir}/test/functional/test_runner.py",
        "-j",
        str(num_procs * 2),
        "--failfast",
        "--combinedlogslen=99999999",
    ])


if __name__ == "__main__":
    main()
