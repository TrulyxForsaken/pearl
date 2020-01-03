import os
from pathlib import Path

import pkg_resources
import shutil

from textwrap import dedent

from pearllib.messenger import messenger, Color
from pearllib.package import remove_package, update_package
from pearllib.pearlenv import PearlEnvironment, PearlOptions
from pearllib.utils import apply, ask, unapply, run_pearl_bash


def init_pearl(pearl_env: PearlEnvironment, _=PearlOptions()):
    """
    Initializes the Pearl environment by setting up the PEARL_HOME configurations.
    """
    messenger.print(
        '{cyan}* {normal}Creating Pearl configuration in {home}'.format(
            cyan=Color.CYAN,
            normal=Color.NORMAL,
            home=pearl_env.home,
        )
    )

    (pearl_env.home / 'bin').mkdir(parents=True, exist_ok=True)
    (pearl_env.home / 'packages').mkdir(parents=True, exist_ok=True)
    (pearl_env.home / 'repos').mkdir(parents=True, exist_ok=True)
    (pearl_env.home / 'tmp').mkdir(parents=True, exist_ok=True)
    (pearl_env.home / 'var').mkdir(parents=True, exist_ok=True)

    if (pearl_env.home / 'bin/pearl').exists():
        (pearl_env.home / 'bin/pearl').unlink()
    (pearl_env.home / 'bin/pearl').symlink_to(pearl_env.root / 'bin/pearl')

    static = Path(pkg_resources.resource_filename('pearllib', 'static/'))

    if not (pearl_env.home / 'pearl.conf').exists():
        pearl_conf_template = static / 'etc/pearl.conf.template'
        shutil.copyfile(str(pearl_conf_template), str(pearl_env.home / 'pearl.conf'))

    apply(
        "export PEARL_ROOT={pearlroot}\nsource {static}/boot/sh/pearl.sh".format(
            pearlroot=pearl_env.root,
            static=static,
        ),
        "{}/.bashrc".format(os.environ['HOME'])
    )
    messenger.print(
        '{cyan}* {normal}Activated Pearl for Bash'.format(
            cyan=Color.CYAN,
            normal=Color.NORMAL,
        )
    )

    apply(
        "export PEARL_ROOT={pearlroot}\nsource {static}/boot/sh/pearl.sh".format(
            pearlroot=pearl_env.root,
            static=static,
        ),
        "{}/.zshrc".format(os.environ['HOME'])
    )
    messenger.print(
        '{cyan}* {normal}Activated Pearl for Zsh'.format(
            cyan=Color.CYAN,
            normal=Color.NORMAL,
        )
    )

    apply(
        "set -x PEARL_ROOT {pearlroot}\nsource {static}/boot/fish/pearl.fish".format(
            pearlroot=pearl_env.root,
            static=static,
        ),
        '{}/.config/fish/config.fish'.format(os.environ['HOME'])
    )
    messenger.print(
        '{cyan}* {normal}Activated Pearl for Fish shell'.format(
            cyan=Color.CYAN,
            normal=Color.NORMAL,
        )
    )

    apply(
        "source {static}/boot/vim/pearl.vim".format(
            static=static,
        ),
        "{}/.vimrc".format(os.environ['HOME'])
    )
    messenger.print(
        '{cyan}* {normal}Activated Pearl for Vim editor'.format(
            cyan=Color.CYAN,
            normal=Color.NORMAL,
        )
    )

    apply(
        "source {static}/boot/emacs/pearl.el".format(static=static),
        "{}/.emacs".format(os.environ['HOME'])
    )
    messenger.print(
        '{cyan}* {normal}Activated Pearl for Emacs editor'.format(
            cyan=Color.CYAN,
            normal=Color.NORMAL,
        )
    )

    messenger.info('')
    messenger.info("Done! Open a new terminal and have fun!")
    messenger.info('')
    messenger.info("To get the list of Pearl packages available:")
    messenger.print("    >> pearl list")


def remove_pearl(pearl_env: PearlEnvironment, options=PearlOptions()):
    """
    Removes completely the Pearl environment.
    """
    static = Path(pkg_resources.resource_filename('pearllib', 'static/'))

    for repo_name, repo_packages in pearl_env.packages.items():
        if options.no_confirm or ask("Are you sure to REMOVE all the installed packages in {} repository?".format(repo_name), "N"):
            for _, package in repo_packages.items():
                if package.is_installed():
                    remove_package(pearl_env, package.full_name, options=options)

    if options.no_confirm or ask("Are you sure to REMOVE all the Pearl hooks?", "N"):
        unapply(
            "export PEARL_ROOT={pearlroot}\nsource {static}/boot/sh/pearl.sh".format(
                pearlroot=pearl_env.root,
                static=static,
            ),
            "{}/.bashrc".format(os.environ['HOME'])
        )
        messenger.print(
            '{cyan}* {normal}Deactivated Pearl for Bash'.format(
                cyan=Color.CYAN,
                normal=Color.NORMAL,
            )
        )

        unapply(
            "export PEARL_ROOT={pearlroot}\nsource {static}/boot/sh/pearl.sh".format(
                pearlroot=pearl_env.root,
                static=static,
            ),
            "{}/.zshrc".format(os.environ['HOME'])
        )
        messenger.print(
            '{cyan}* {normal}Deactivated Pearl for Zsh'.format(
                cyan=Color.CYAN,
                normal=Color.NORMAL,
            )
        )

        unapply(
            "set -x PEARL_ROOT {pearlroot}\nsource {static}/boot/fish/pearl.fish".format(
                pearlroot=pearl_env.root,
                static=static,
            ),
            '{}/.config/fish/config.fish'.format(os.environ['HOME'])
        )
        messenger.print(
            '{cyan}* {normal}Deactivated Pearl for Fish shell'.format(
                cyan=Color.CYAN,
                normal=Color.NORMAL,
            )
        )

        unapply(
            "source {static}/boot/vim/pearl.vim".format(static=static),
            "{}/.vimrc".format(os.environ['HOME'])
        )
        messenger.print(
            '{cyan}* {normal}Deactivated Pearl for Vim editor'.format(
                cyan=Color.CYAN,
                normal=Color.NORMAL,
            )
        )

        unapply(
            "source {static}/boot/emacs/pearl.el".format(static=static),
            "{}/.emacs".format(os.environ['HOME'])
        )
        messenger.print(
            '{cyan}* {normal}Deactivated Pearl for Emacs editor'.format(
                cyan=Color.CYAN,
                normal=Color.NORMAL,
            )
        )

    if options.no_confirm or ask("Are you sure to REMOVE the Pearl config $PEARL_HOME directory (NOT RECOMMENDED)?", "N"):
        shutil.rmtree(str(pearl_env.home))


def update_pearl(pearl_env: PearlEnvironment, options=PearlOptions()):
    """Updates the Pearl environment."""
    if options.no_confirm or ask("Do you want to update Pearl main codebase located in {}?".format(pearl_env.root), "Y"):
        messenger.print(
            '{cyan}* {normal}Updating Pearl script'.format(
                cyan=Color.CYAN,
                normal=Color.NORMAL,
            )
        )
        quiet = "false" if options.verbose else "true"
        script = dedent(
            """
            update_git_repo {pearlroot} "master" {quiet}
            """
        ).format(
            pearlroot=pearl_env.root,
            quiet=quiet)
        run_pearl_bash(script, pearl_env, input='' if options.no_confirm else None)

    for repo_name, repo_packages in pearl_env.packages.items():
        for _, package in repo_packages.items():
            if package.is_installed():
                update_package(pearl_env, package.full_name, options=options)
