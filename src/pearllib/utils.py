import subprocess
import shutil

from pathlib import Path

from textwrap import dedent

import pkg_resources

from pearllib.messenger import messenger
from pearllib.pearlenv import PearlEnvironment

_BASH_SCRIPT_HEADER_TEMPLATE = dedent("""
set -e -o pipefail

# PATH needs to be updated since GNU Coreutils is required in OSX
# environments. Buava `osx_update_path` cannot be used because in
# order to load osx-compat.sh file the `readlink` command is
# required first (circular dependency).
COREUTILS_GNUBIN="/usr/local/opt/coreutils/libexec/gnubin"
[[ -d "$COREUTILS_GNUBIN" ]] && PATH="$COREUTILS_GNUBIN:$PATH"

PEARL_ROOT="{pearlroot}"
PEARL_HOME="{pearlhome}"

cd "$PEARL_HOME"

source "{static}"/buava/lib/utils.sh
source "{static}"/buava/lib/osx-compat.sh
source "{static}"/builtins/utils.sh

""")


def run_bash(
        script: str,
        capture_stdout=False, capture_stderr=False,
        check=True, input:str = None
):
    return subprocess.run(
        ['/usr/bin/env', 'bash', '-c', script],
        check=check,
        stdout=subprocess.PIPE if capture_stdout else None,
        stderr=subprocess.PIPE if capture_stderr else None,
        universal_newlines=True,
        input=input,
    )


def run_pearl_bash(
        script: str, pearl_env: PearlEnvironment,
        capture_stdout=False, capture_stderr=False,
        check=True,
        input: str = None,
):
    """Runs a bash script within the Pearl ecosystem."""

    bash_header = _BASH_SCRIPT_HEADER_TEMPLATE.format(
        pearlroot=pearl_env.root,
        pearlhome=pearl_env.home,
        static=pkg_resources.resource_filename('pearllib', 'static/'),
    )
    script = '{bashheader}\n{script}'.format(
        bashheader=bash_header,
        script=script,
    )
    return run_bash(script, capture_stdout=capture_stdout, capture_stderr=capture_stderr, check=check, input=input)


def verify_git_dep():
    git_version_min = 'git version 1.8.5'
    obj = run_bash("git version", capture_stdout=True, check=False)
    git_version = obj.stdout.strip() if obj.stdout else None
    git_status = obj.returncode
    if git_status == 127:
        raise EnvironmentError('The command git has not been found. Exiting...')

    if git_version < git_version_min:
        messenger.warn(
            "Pearl might not work properly since git is too old: {} < {}".format(
                git_version, git_version_min
            )
        )
        return False

    return True


def verify_bash_dep():
    bash_version_min = "4.1"
    obj = run_bash("echo $BASH_VERSION", capture_stdout=True, check=False)
    bash_version = obj.stdout.strip() if obj.stdout else None
    bash_status = obj.returncode
    if bash_status == 127:
        raise EnvironmentError('The command bash has not been found. Exiting...')
    if bash_version is None:
        messenger.warn(
            "Warn: The BASH_VERSION environment variable is not defined"
        )
        return False
    elif bash_version < bash_version_min:
        messenger.warn(
            "Warn: Pearl might not work properly since bash is too old: {} < {}".format(
                bash_version, bash_version_min
            )
        )
        return False
    return True


def verify_runtime_deps():
    verify_git_dep()
    verify_bash_dep()


def check_and_copy(src_dir: Path, dst_dir: Path):
    """
    Checks if src_dir exists and removes the dst_dir content before copying.
    """
    if not src_dir.is_dir():
        raise NotADirectoryError('{} is not a directory'.format(src_dir))
    shutil.rmtree(str(dst_dir))
    shutil.copytree(str(src_dir), str(dst_dir))


def ask(prompt: str, yes_as_default_answer: bool = False, no_confirm: bool = False):
    """
    Ask a question and wait to receive an answer from stdin.
    It returns yes_as_default_answer if no answer has been received from stdin.
    """
    if no_confirm:
        return yes_as_default_answer

    if yes_as_default_answer:
        default_answer = "Y"
        other_answer = "n"
    else:
        default_answer = "N"
        other_answer = "y"

    answer = None
    while answer not in ['Y', 'N']:
        answer = input(messenger.info('{} ({}/{})'.format(prompt, default_answer, other_answer))).upper()
        if not answer:
            answer = default_answer

    return answer == "Y"


def apply(line: str, filename: str):
    """
    Applies a string to a file.
    The function is idempotent, so calling this function multiple
    times will apply the string once.
    If filename does not exist, the function will create the file and all its
    parent directories (if needed).
    """
    path = Path(filename)
    path.parent.mkdir(parents=True, exist_ok=True)

    if not path.exists():
        path.touch()
    with path.open("r+") as f:
        content = f.read()
        if line not in content.split('\n'):
            f.seek(0)
            f.write("{}\n{}".format(line, content))


def unapply(line: str, filename: str):
    """
    Unapply a string to a file.
    The function is idempotent, so calling this function multiple
    times will remove the string entirely and if the string does not exist
    it will return successfully.
    If filename does not exist, the function will return successfully.
    """
    path = Path(filename)
    if not path.exists():
        return
    with path.open("r+") as f:
        writeable_content = f.read().replace(line + '\n', '').replace(line, "")
    with path.open("w") as f:
        f.write(writeable_content)
