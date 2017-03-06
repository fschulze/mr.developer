import os
import pytest
import shutil
import tempfile


class Path(str):
    def __getitem__(self, name):
        return Path(os.path.join(self, name))

    def create_file(self, *content):
        f = open(self, 'w')
        f.write('\n'.join(content))
        f.close()


@pytest.fixture
def src(tempdir):
    base = tempdir['src']
    os.mkdir(base)
    return base


@pytest.fixture
def tempdir():
    cwd = os.getcwd()
    tempdir = os.path.realpath(tempfile.mkdtemp())
    try:
        os.chdir(tempdir)
        try:
            yield Path(tempdir)
        finally:
            os.chdir(cwd)
    finally:
        shutil.rmtree(tempdir)


@pytest.fixture
def mkgitrepo(tempdir):
    from mr.developer.tests.utils import GitRepo

    def mkgitrepo(name):
        repository = GitRepo(tempdir[name])
        repository.init()
        repository.setup_user()
        return repository

    return mkgitrepo


@pytest.fixture
def develop(src):
    from mr.developer.tests.utils import MockDevelop
    develop = MockDevelop()
    develop.sources_dir = src
    return develop
