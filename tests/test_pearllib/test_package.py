from unittest import mock

import pytest

from pearllib.exceptions import RepoDoesNotExistError, PackageNotInRepoError, PackageAlreadyInstalledError, \
    HookFunctionError, PackageNotInstalledError
from pearllib.package import install_package, remove_package, list_packages, update_package, emerge_package
from pearllib.pearlenv import Package, PearlOptions

from .utils import create_pearl_env, create_pearl_home, create_pearl_root

_MODULE_UNDER_TEST = 'pearllib.package'


class PackageBuilder:
    def __init__(self, home_dir):
        self.packages = {}
        self.home_dir =home_dir

    def add_local_package(
            self,
            tmp_path, install_sh_script,
            repo_name='repo-test',
            package_name='pkg-test',
            is_installed=False,
    ):
        """Install a package somewhere locally"""
        pkg_dir = tmp_path / '{}/{}'.format(repo_name, package_name)
        (pkg_dir / 'pearl-config').mkdir(parents=True)
        install_sh = pkg_dir / 'pearl-config/install.sh'
        install_sh.touch()
        install_sh.write_text(install_sh_script)

        if is_installed:
            self._install_package(
                install_sh_script,
                repo_name=repo_name,
                package_name=package_name,
            )

        package = Package(self.home_dir, repo_name, package_name, str(pkg_dir), '')
        self._update_packages(package)

    def add_git_package(
            self,
            install_sh_script,
            repo_name='repo-test',
            package_name='pkg-test',
            url='https://github.com/pkg',
            is_installed=False,
    ):

        if is_installed:
            self._install_package(
                install_sh_script,
                repo_name='repo-test',
                package_name='pkg-test',
            )
        package = Package(self.home_dir, repo_name, package_name, url, '')
        self._update_packages(package)

    def build(self):
        return self.packages

    def _update_packages(self, package: Package):
        if package.repo_name not in self.packages:
            self.packages[package.repo_name] = {}
        self.packages[package.repo_name][package.name] = package

    def _install_package(
            self,
            install_sh_script,
            repo_name='repo-test',
            package_name='pkg-test',
    ):
        pkg_dir = self.home_dir / 'packages/{}/{}'.format(repo_name, package_name)
        (pkg_dir / 'pearl-config').mkdir(parents=True)
        install_sh = pkg_dir / 'pearl-config/install.sh'
        install_sh.write_text(install_sh_script)


def test_install_local_package(tmp_path):
    home_dir = create_pearl_home(tmp_path)
    root_dir = create_pearl_root(tmp_path)
    install_sh_script = """
    post_install() {{
        echo $PWD > {homedir}/result
        echo $PEARL_HOME >> {homedir}/result
        echo $PEARL_ROOT >> {homedir}/result
        echo $PEARL_PKGDIR >> {homedir}/result
        echo $PEARL_PKGVARDIR >> {homedir}/result
        echo $PEARL_PKGNAME >> {homedir}/result
        echo $PEARL_PKGREPONAME >> {homedir}/result
        return 0
    }}
    """.format(homedir=home_dir)

    builder = PackageBuilder(home_dir)
    builder.add_local_package(tmp_path, install_sh_script, is_installed=False)
    packages = builder.build()
    package = packages['repo-test']['pkg-test']

    pearl_env = create_pearl_env(home_dir, root_dir, packages)

    install_package(pearl_env, 'repo-test/pkg-test')

    assert (home_dir / 'packages/repo-test/pkg-test/pearl-config/install.sh').is_file()
    assert (home_dir / 'var/repo-test/pkg-test').is_dir()

    expected_result = """{}\n{}\n{}\n{}\n{}\n{}\n{}\n""".format(
        package.dir, home_dir, root_dir, package.dir, package.vardir,
        package.name, package.repo_name
    )
    assert (home_dir / 'result').read_text() == expected_result


def test_install_local_package_no_confirm(tmp_path):
    home_dir = create_pearl_home(tmp_path)
    root_dir = create_pearl_root(tmp_path)
    install_sh_script = """
    post_install() {{
        if ask "Are you sure?" "Y"
        then
            echo "YES" > {homedir}/result
        else
            echo "NO" > {homedir}/result
        fi
        
        local choice=$(choose "What?" "banana" "apple" "banana" "orange")
        echo "$choice" >> {homedir}/result
        return 0
    }}
    """.format(homedir=home_dir)

    builder = PackageBuilder(home_dir)
    builder.add_local_package(tmp_path, install_sh_script, is_installed=False)
    packages = builder.build()

    pearl_env = create_pearl_env(home_dir, root_dir, packages)

    install_package(pearl_env, 'repo-test/pkg-test', PearlOptions(no_confirm=True, verbose=False))

    assert (home_dir / 'result').read_text() == "YES\nbanana\n"


def test_install_package_git(tmp_path):
    home_dir = create_pearl_home(tmp_path)
    root_dir = create_pearl_root(tmp_path)

    builder = PackageBuilder(home_dir)
    builder.add_git_package("", is_installed=False)
    packages = builder.build()
    pearl_env = create_pearl_env(home_dir, root_dir, packages)

    with mock.patch(_MODULE_UNDER_TEST + ".run_pearl_bash") as run_mock:
        install_package(pearl_env, 'repo-test/pkg-test')

        assert run_mock.call_count == 2
        assert (home_dir / 'var/repo-test/pkg-test').is_dir()


def test_install_package_raise_hook(tmp_path):
    home_dir = create_pearl_home(tmp_path)
    root_dir = create_pearl_root(tmp_path)
    install_sh_script = """
    post_install() {{
        command-notfound
        return 0
    }}
    """

    builder = PackageBuilder(home_dir)
    builder.add_local_package(tmp_path, install_sh_script, is_installed=False)
    packages = builder.build()
    pearl_env = create_pearl_env(home_dir, root_dir, packages)

    with pytest.raises(HookFunctionError):
        install_package(pearl_env, 'repo-test/pkg-test')


def test_install_package_repo_not_exist(tmp_path):
    home_dir = create_pearl_home(tmp_path)
    root_dir = create_pearl_root(tmp_path)
    pearl_env = create_pearl_env(home_dir, root_dir, {})

    with pytest.raises(RepoDoesNotExistError):
        install_package(pearl_env, 'test/pkg-test')


def test_install_package_package_not_exist(tmp_path):
    home_dir = create_pearl_home(tmp_path)
    root_dir = create_pearl_root(tmp_path)

    builder = PackageBuilder(home_dir)
    builder.add_local_package(tmp_path, "", is_installed=False)
    packages = builder.build()
    pearl_env = create_pearl_env(home_dir, root_dir, packages)
    with pytest.raises(PackageNotInRepoError):
        install_package(pearl_env, 'repo-test/pkg-a-test')

    with pytest.raises(PackageNotInRepoError):
        install_package(pearl_env, 'pkg-a-test')


def test_install_package_already_installed(tmp_path):
    home_dir = create_pearl_home(tmp_path)
    root_dir = create_pearl_root(tmp_path)

    builder = PackageBuilder(home_dir)
    builder.add_local_package(tmp_path, "", is_installed=True)
    packages = builder.build()
    pearl_env = create_pearl_env(home_dir, root_dir, packages)

    with pytest.raises(PackageAlreadyInstalledError):
        install_package(pearl_env, 'repo-test/pkg-test')


def test_update_local_package(tmp_path):
    home_dir = create_pearl_home(tmp_path)
    root_dir = create_pearl_root(tmp_path)
    install_sh_script = """
    pre_update() {{
        echo $PWD > {homedir}/result
        echo $PEARL_HOME >> {homedir}/result
        echo $PEARL_ROOT >> {homedir}/result
        echo $PEARL_PKGDIR >> {homedir}/result
        echo $PEARL_PKGVARDIR >> {homedir}/result
        echo $PEARL_PKGNAME >> {homedir}/result
        echo $PEARL_PKGREPONAME >> {homedir}/result
        return 0
    }}
    
    post_update() {{
        echo $PWD > {homedir}/result2
        echo $PEARL_HOME >> {homedir}/result2
        echo $PEARL_ROOT >> {homedir}/result2
        echo $PEARL_PKGDIR >> {homedir}/result2
        echo $PEARL_PKGVARDIR >> {homedir}/result2
        echo $PEARL_PKGNAME >> {homedir}/result2
        echo $PEARL_PKGREPONAME >> {homedir}/result2
        return 0
    }}
    
    """.format(homedir=home_dir)

    builder = PackageBuilder(home_dir)
    builder.add_local_package(tmp_path, install_sh_script, is_installed=True)
    packages = builder.build()
    package = packages['repo-test']['pkg-test']

    pearl_env = create_pearl_env(home_dir, root_dir, packages)

    update_package(pearl_env, 'repo-test/pkg-test')

    assert (home_dir / 'packages/repo-test/pkg-test/pearl-config/install.sh').is_file()

    expected_result = """{}\n{}\n{}\n{}\n{}\n{}\n{}\n""".format(
        package.dir, home_dir, root_dir, package.dir, package.vardir,
        package.name, package.repo_name
    )
    assert (home_dir / 'result').read_text() == expected_result

    expected_result = """{}\n{}\n{}\n{}\n{}\n{}\n{}\n""".format(
        package.dir, home_dir, root_dir, package.dir, package.vardir,
        package.name, package.repo_name
    )
    assert (home_dir / 'result2').read_text() == expected_result


def test_update_local_package_no_confirm(tmp_path):
    home_dir = create_pearl_home(tmp_path)
    root_dir = create_pearl_root(tmp_path)
    install_sh_script = """
    pre_update() {{
        if ask "Are you sure?" "Y"
        then
            echo "YES" > {homedir}/result
        else
            echo "NO" > {homedir}/result
        fi

        local choice=$(choose "What?" "banana" "apple" "banana" "orange")
        echo "$choice" >> {homedir}/result
        return 0
    }}
    post_update() {{
        if ask "Are you sure?" "N"
        then
            echo "YES" > {homedir}/result2
        else
            echo "NO" > {homedir}/result2
        fi

        local choice=$(choose "What?" "orange" "apple" "banana" "orange")
        echo "$choice" >> {homedir}/result2
        return 0
    }}
    """.format(homedir=home_dir)

    builder = PackageBuilder(home_dir)
    builder.add_local_package(tmp_path, install_sh_script, is_installed=True)
    packages = builder.build()

    pearl_env = create_pearl_env(home_dir, root_dir, packages)

    update_package(pearl_env, 'repo-test/pkg-test', PearlOptions(no_confirm=True, verbose=False))

    assert (home_dir / 'result').read_text() == "YES\nbanana\n"
    assert (home_dir / 'result2').read_text() == "NO\norange\n"


def test_update_package_git_url_not_changed(tmp_path):
    home_dir = create_pearl_home(tmp_path)
    root_dir = create_pearl_root(tmp_path)

    builder = PackageBuilder(home_dir)
    builder.add_git_package("", is_installed=True)
    packages = builder.build()
    package = packages['repo-test']['pkg-test']
    pearl_env = create_pearl_env(home_dir, root_dir, packages)

    with mock.patch(_MODULE_UNDER_TEST + ".run_pearl_bash") as run_mock:
        run_mock.return_value = package.url
        update_package(pearl_env, 'repo-test/pkg-test')

        assert run_mock.call_count == 4


def test_update_package_git_url_changed(tmp_path):
    home_dir = create_pearl_home(tmp_path)
    root_dir = create_pearl_root(tmp_path)

    builder = PackageBuilder(home_dir)
    builder.add_git_package("", is_installed=True)
    packages = builder.build()
    pearl_env = create_pearl_env(home_dir, root_dir, packages)

    with mock.patch(_MODULE_UNDER_TEST + ".run_pearl_bash") as run_mock, \
            mock.patch(_MODULE_UNDER_TEST + ".ask") as ask_mock, \
            mock.patch(_MODULE_UNDER_TEST + ".remove_package") as remove_mock, \
            mock.patch(_MODULE_UNDER_TEST + ".install_package") as install_mock:
        run_mock.return_value = 'https://github.com/package'
        ask_mock.return_value = False

        update_package(pearl_env, 'repo-test/pkg-test')

        assert ask_mock.call_count == 1
        assert remove_mock.call_count == 0
        assert install_mock.call_count == 0
        assert run_mock.call_count == 4

    with mock.patch(_MODULE_UNDER_TEST + ".run_pearl_bash") as run_mock, \
            mock.patch(_MODULE_UNDER_TEST + ".ask") as ask_mock, \
            mock.patch(_MODULE_UNDER_TEST + ".remove_package") as remove_mock, \
            mock.patch(_MODULE_UNDER_TEST + ".install_package") as install_mock:
        run_mock.return_value = 'https://github.com/package'
        ask_mock.return_value = True

        update_package(pearl_env, 'repo-test/pkg-test')

        assert ask_mock.call_count == 1
        assert remove_mock.call_count == 1
        assert install_mock.call_count == 1
        assert run_mock.call_count == 4


def test_update_package_raise_hook(tmp_path):
    home_dir = create_pearl_home(tmp_path)
    root_dir = create_pearl_root(tmp_path)
    install_sh_script = """
    pre_update() {{
        command-notfound
        return 0
    }}
    """

    builder = PackageBuilder(home_dir)
    builder.add_local_package(tmp_path, install_sh_script, is_installed=True)
    packages = builder.build()
    pearl_env = create_pearl_env(home_dir, root_dir, packages)

    with pytest.raises(HookFunctionError):
        update_package(pearl_env, 'repo-test/pkg-test')


def test_update_package_repo_not_exist(tmp_path):
    home_dir = create_pearl_home(tmp_path)
    root_dir = create_pearl_root(tmp_path)
    pearl_env = create_pearl_env(home_dir, root_dir, {})

    with pytest.raises(RepoDoesNotExistError):
        update_package(pearl_env, 'test/pkg-test')


def test_update_package_package_not_exist(tmp_path):
    home_dir = create_pearl_home(tmp_path)
    root_dir = create_pearl_root(tmp_path)

    builder = PackageBuilder(home_dir)
    builder.add_local_package(tmp_path, "", is_installed=True)
    packages = builder.build()
    pearl_env = create_pearl_env(home_dir, root_dir, packages)
    with pytest.raises(PackageNotInRepoError):
        update_package(pearl_env, 'repo-test/pkg-a-test')

    with pytest.raises(PackageNotInRepoError):
        update_package(pearl_env, 'pkg-a-test')


def test_update_package_not_installed(tmp_path):
    home_dir = create_pearl_home(tmp_path)
    root_dir = create_pearl_root(tmp_path)

    builder = PackageBuilder(home_dir)
    builder.add_local_package(tmp_path, "", is_installed=False)
    packages = builder.build()
    pearl_env = create_pearl_env(home_dir, root_dir, packages)

    with pytest.raises(PackageNotInstalledError):
        update_package(pearl_env, 'repo-test/pkg-test')


def test_emerge_package(tmp_path):
    home_dir = create_pearl_home(tmp_path)
    root_dir = create_pearl_root(tmp_path)

    builder = PackageBuilder(home_dir)
    builder.add_local_package(tmp_path, "", package_name='pkg-a-test', is_installed=False)
    builder.add_local_package(tmp_path, "", package_name='pkg-b-test', is_installed=True)
    packages = builder.build()
    pearl_env = create_pearl_env(home_dir, root_dir, packages)

    with mock.patch(_MODULE_UNDER_TEST + ".update_package") as update_mock, \
            mock.patch(_MODULE_UNDER_TEST + ".install_package") as install_mock:
        emerge_package(pearl_env, 'repo-test/pkg-a-test')
        assert update_mock.call_count == 0
        assert install_mock.call_count == 1

    with mock.patch(_MODULE_UNDER_TEST + ".update_package") as update_mock, \
            mock.patch(_MODULE_UNDER_TEST + ".install_package") as install_mock:
        emerge_package(pearl_env, 'repo-test/pkg-b-test')
        assert update_mock.call_count == 1
        assert install_mock.call_count == 0


def test_remove_package(tmp_path):
    home_dir = create_pearl_home(tmp_path)
    root_dir = create_pearl_root(tmp_path)

    install_sh_script = """
    pre_remove() {{
        echo $PWD > {homedir}/result
        echo $PEARL_HOME >> {homedir}/result
        echo $PEARL_ROOT >> {homedir}/result
        echo $PEARL_PKGDIR >> {homedir}/result
        echo $PEARL_PKGVARDIR >> {homedir}/result
        echo $PEARL_PKGNAME >> {homedir}/result
        echo $PEARL_PKGREPONAME >> {homedir}/result
        return 0
    }}
    """.format(homedir=home_dir)

    builder = PackageBuilder(home_dir)
    builder.add_local_package(tmp_path, install_sh_script, is_installed=True)
    packages = builder.build()
    package = packages['repo-test']['pkg-test']

    pearl_env = create_pearl_env(home_dir, root_dir, packages)

    remove_package(pearl_env, 'repo-test/pkg-test')

    assert not (home_dir / 'packages/repo-test/pkg-test/').exists()

    expected_result = """{}\n{}\n{}\n{}\n{}\n{}\n{}\n""".format(
        package.dir, home_dir, root_dir,
        package.dir, package.vardir, package.name, package.repo_name
    )
    assert (home_dir / 'result').read_text() == expected_result


def test_remove_package_no_confirm(tmp_path):
    home_dir = create_pearl_home(tmp_path)
    root_dir = create_pearl_root(tmp_path)

    install_sh_script = """
    pre_remove() {{
        if ask "Are you sure?" "Y"
        then
            echo "YES" > {homedir}/result
        else
            echo "NO" > {homedir}/result
        fi

        local choice=$(choose "What?" "banana" "apple" "banana" "orange")
        echo "$choice" >> {homedir}/result
        return 0
    }}
    """.format(homedir=home_dir)

    builder = PackageBuilder(home_dir)
    builder.add_local_package(tmp_path, install_sh_script, is_installed=True)
    packages = builder.build()

    pearl_env = create_pearl_env(home_dir, root_dir, packages)

    remove_package(pearl_env, 'repo-test/pkg-test', PearlOptions(no_confirm=True, verbose=False))

    assert (home_dir / 'result').read_text() == "YES\nbanana\n"


def test_remove_package_raise_hook(tmp_path):
    home_dir = create_pearl_home(tmp_path)
    root_dir = create_pearl_root(tmp_path)
    install_sh_script = """
    pre_remove() {{
        command-notfound
        return 0
    }}
    """

    builder = PackageBuilder(home_dir)
    builder.add_local_package(tmp_path, install_sh_script, is_installed=True)
    packages = builder.build()
    pearl_env = create_pearl_env(home_dir, root_dir, packages)

    with pytest.raises(HookFunctionError):
        remove_package(pearl_env, 'repo-test/pkg-test')


def test_remove_package_repo_not_exist(tmp_path):
    home_dir = create_pearl_home(tmp_path)
    root_dir = create_pearl_root(tmp_path)
    pearl_env = create_pearl_env(home_dir, root_dir, {})

    with pytest.raises(RepoDoesNotExistError):
        remove_package(pearl_env, 'test/pkg-test')


def test_remove_package_package_not_exist(tmp_path):
    home_dir = create_pearl_home(tmp_path)
    root_dir = create_pearl_root(tmp_path)

    builder = PackageBuilder(home_dir)
    builder.add_local_package(tmp_path, "", is_installed=True)
    packages = builder.build()
    pearl_env = create_pearl_env(home_dir, root_dir, packages)
    with pytest.raises(PackageNotInRepoError):
        remove_package(pearl_env, 'repo-test/pkg-a-test')

    with pytest.raises(PackageNotInRepoError):
        remove_package(pearl_env, 'pkg-a-test')


def test_remove_package_not_installed(tmp_path):
    home_dir = create_pearl_home(tmp_path)
    root_dir = create_pearl_root(tmp_path)

    builder = PackageBuilder(home_dir)
    builder.add_local_package(tmp_path, "", is_installed=False)
    packages = builder.build()
    pearl_env = create_pearl_env(home_dir, root_dir, packages)

    with pytest.raises(PackageNotInstalledError):
        remove_package(pearl_env, 'repo-test/pkg-test')


def test_list_packages(tmp_path):
    home_dir = create_pearl_home(tmp_path)
    (home_dir / 'packages/repo-test/pkg-a-test').mkdir(parents=True)

    pearl_env = mock.Mock()
    pearl_env.packages = {
        'repo-test': {
            'pkg-a-test': Package(home_dir, 'repo-test', 'pkg-a-test', 'url', 'descr'),
            'pkg-b-test': Package(home_dir, 'repo-test', 'pkg-b-test', 'url', 'descr'),
        }
    }
    list_packages(pearl_env, 'pkg')