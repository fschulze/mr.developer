from mr.developer.extension import Source
from mr.developer.tests.utils import Process
from unittest.mock import patch

import os
import pytest
import shutil


class TestGit:
    def createDefaultContent(self, repository):
        # Create default content and branches in a repository.
        # Return a revision number.
        repository.add_file("foo", msg="Initial")
        # create branch for testing
        repository("git checkout -b test", echo=False)
        repository.add_file("foo2")
        # get comitted rev
        lines = repository("git log", echo=False)
        rev = lines[0].split()[1]
        # return to default branch
        repository("git checkout master", echo=False)
        repository.add_file("bar")
        # Return revision of one of the commits, the one that adds the
        # foo2 file.
        return rev

    def testUpdateWithRevisionPin(self, develop, mkgitrepo, src):
        from mr.developer.commands import CmdCheckout
        from mr.developer.commands import CmdUpdate

        repository = mkgitrepo("repository")
        rev = self.createDefaultContent(repository)

        # check rev
        develop.sources = {
            "egg": Source(
                kind="git",
                name="egg",
                rev=rev,
                url="%s" % repository.base,
                path=src["egg"],
            )
        }
        CmdCheckout(develop)(develop.parser.parse_args(["co", "egg"]))
        assert set(os.listdir(src["egg"])) == {".git", "foo", "foo2"}
        CmdUpdate(develop)(develop.parser.parse_args(["up", "egg"]))
        assert set(os.listdir(src["egg"])) == {".git", "foo", "foo2"}

        shutil.rmtree(src["egg"])

    def testUpdateWithBranch(self, develop, mkgitrepo, src):
        from mr.developer.commands import CmdCheckout
        from mr.developer.commands import CmdStatus
        from mr.developer.commands import CmdUpdate

        repository = mkgitrepo("repository")
        self.createDefaultContent(repository)

        # check branch
        develop.sources = {
            "egg": Source(
                kind="git",
                name="egg",
                branch="test",
                url="%s" % repository.base,
                path=src["egg"],
            )
        }
        CmdCheckout(develop)(develop.parser.parse_args(["co", "egg"]))
        assert set(os.listdir(src["egg"])) == {".git", "foo", "foo2"}
        CmdUpdate(develop)(develop.parser.parse_args(["up", "egg"]))
        assert set(os.listdir(src["egg"])) == {".git", "foo", "foo2"}
        CmdStatus(develop)(develop.parser.parse_args(["status"]))

    def testUpdateWithMain(self, develop, mkgitrepo, src):
        from mr.developer.commands import CmdCheckout
        from mr.developer.commands import CmdUpdate

        repository = mkgitrepo("repository")
        self.createDefaultContent(repository)
        develop.sources = {
            "egg": Source(
                kind="git", name="egg", url="%s" % repository.base, path=src["egg"]
            )
        }
        CmdCheckout(develop)(develop.parser.parse_args(["co", "egg"]))
        assert set(os.listdir(src["egg"])) == {".git", "bar", "foo"}
        CmdUpdate(develop)(develop.parser.parse_args(["up", "egg"]))
        assert set(os.listdir(src["egg"])) == {".git", "bar", "foo"}

    def testRaiseExceptionUpdateWithRevisionAndBranch(self, develop, mkgitrepo, src):
        from mr.developer.commands import CmdCheckout

        repository = mkgitrepo("repository")
        rev = self.createDefaultContent(repository)
        # we can't use both rev and branch
        with pytest.raises(SystemExit):
            develop.sources = {
                "egg": Source(
                    kind="git",
                    name="egg",
                    branch="test",
                    rev=rev,
                    url="%s" % repository.base,
                    path=src["egg-failed"],
                )
            }
            CmdCheckout(develop)(develop.parser.parse_args(["co", "egg"]))

    def testUpdateWithoutRevisionPin(self, develop, mkgitrepo, src, capsys):
        from mr.developer.commands import CmdCheckout
        from mr.developer.commands import CmdStatus
        from mr.developer.commands import CmdUpdate

        repository = mkgitrepo("repository")
        repository.add_file("foo")
        repository.add_file("bar")
        repository.add_branch("develop")
        develop.sources = {
            "egg": Source(kind="git", name="egg", url=repository.url, path=src["egg"])
        }
        _log = patch("mr.developer.git.logger")
        log = _log.__enter__()
        try:
            CmdCheckout(develop)(develop.parser.parse_args(["co", "egg"]))
            assert set(os.listdir(src["egg"])) == {".git", "bar", "foo"}
            captured = capsys.readouterr()
            assert captured.out.startswith("Initialized empty Git repository in")
            CmdUpdate(develop)(develop.parser.parse_args(["up", "egg"]))
            assert set(os.listdir(src["egg"])) == {".git", "bar", "foo"}
            assert log.method_calls == [
                ("info", ("Cloned 'egg' with git from '%s'." % repository.url,), {}),
                ("info", ("Updated 'egg' with git.",), {}),
                ("info", ("Switching to remote branch 'remotes/origin/master'.",), {}),
            ]
            captured = capsys.readouterr()
            assert captured.out == ""
            CmdStatus(develop)(develop.parser.parse_args(["status", "-v"]))
            captured = capsys.readouterr()
            assert captured.out == "~   A egg\n      ## master...origin/master\n\n"

        finally:
            _log.__exit__(None, None, None)

    def testUpdateVerbose(self, develop, mkgitrepo, src, capsys):
        from mr.developer.commands import CmdCheckout
        from mr.developer.commands import CmdStatus
        from mr.developer.commands import CmdUpdate

        repository = mkgitrepo("repository")
        repository.add_file("foo")
        repository.add_file("bar")
        repository.add_branch("develop")
        develop.sources = {
            "egg": Source(kind="git", name="egg", url=repository.url, path=src["egg"])
        }
        _log = patch("mr.developer.git.logger")
        log = _log.__enter__()
        try:
            CmdCheckout(develop)(develop.parser.parse_args(["co", "egg", "-v"]))
            assert set(os.listdir(src["egg"])) == {".git", "bar", "foo"}
            captured = capsys.readouterr()
            assert captured.out.startswith("Initialized empty Git repository in")
            CmdUpdate(develop)(develop.parser.parse_args(["up", "egg", "-v"]))
            assert set(os.listdir(src["egg"])) == {".git", "bar", "foo"}
            assert log.method_calls == [
                ("info", ("Cloned 'egg' with git from '%s'." % repository.url,), {}),
                ("info", ("Updated 'egg' with git.",), {}),
                ("info", ("Switching to remote branch 'remotes/origin/master'.",), {}),
            ]
            captured = capsys.readouterr()
            # git output varies between versions...
            git_outputs = [
                "* develop\n  remotes/origin/HEAD -> origin/develop\n  remotes/origin/develop\n  remotes/origin/master\nBranch master set up to track remote branch master from origin.\n  develop\n* master\n  remotes/origin/HEAD -> origin/develop\n  remotes/origin/develop\n  remotes/origin/master\nAlready up-to-date.\n\n",
                "* develop\n  remotes/origin/HEAD -> origin/develop\n  remotes/origin/develop\n  remotes/origin/master\nBranch 'master' set up to track remote branch 'master' from 'origin'.\n  develop\n* master\n  remotes/origin/HEAD -> origin/develop\n  remotes/origin/develop\n  remotes/origin/master\nAlready up to date.\n\n",
                "* develop\n  remotes/origin/HEAD -> origin/develop\n  remotes/origin/develop\n  remotes/origin/master\nbranch 'master' set up to track 'origin/master'.\n  develop\n* master\n  remotes/origin/HEAD -> origin/develop\n  remotes/origin/develop\n  remotes/origin/master\nAlready up to date.\n\n",
                "* develop\n  remotes/origin/HEAD -> origin/develop\n  remotes/origin/develop\n  remotes/origin/master\nbranch 'master' set up to track 'origin/master' by rebasing.\n  develop\n* master\n  remotes/origin/HEAD -> origin/develop\n  remotes/origin/develop\n  remotes/origin/master\nAlready up to date.\n\n",
            ]
            assert captured.out in git_outputs
            CmdStatus(develop)(develop.parser.parse_args(["status", "-v"]))
            captured = capsys.readouterr()
            assert captured.out == "~   A egg\n      ## master...origin/master\n\n"

        finally:
            _log.__exit__(None, None, None)

    def testDepthOption(self, mkgitrepo, src, tempdir):
        from mr.developer.develop import develop

        # create repository and make two commits on it
        repository = mkgitrepo("repository")
        self.createDefaultContent(repository)

        tempdir["buildout.cfg"].create_file(
            "[buildout]",
            "mr.developer-threads = 1",
            "[sources]",
            "egg = git %s" % repository.url,
        )
        tempdir[".mr.developer.cfg"].create_file()
        # os.chdir(self.tempdir)
        develop("co", "egg")

        # check that there are two commits in history
        egg_process = Process(cwd=src["egg"])
        lines = egg_process.check_call("git log", echo=False)
        commits = [msg for msg in lines if msg.decode("utf-8").startswith("commit")]
        assert len(commits) == 2

        shutil.rmtree(src["egg"])

        tempdir["buildout.cfg"].create_file(
            "[buildout]",
            "mr.developer-threads = 1",
            "[sources]",
            "egg = git %s depth=1" % repository.url,
        )
        develop("co", "egg")

        # check that there is only one commit in history
        lines = egg_process.check_call("git log", echo=False)
        commits = [msg for msg in lines if msg.decode("utf-8").startswith("commit")]
        assert len(commits) == 1

        shutil.rmtree(src["egg"])

        tempdir["buildout.cfg"].create_file(
            "[buildout]",
            "mr.developer-threads = 1",
            "git-clone-depth = 1",
            "[sources]",
            "egg = git %s" % repository.url,
        )
        develop("co", "egg")

        # check that there is only one commit in history
        lines = egg_process.check_call("git log", echo=False)
        commits = [msg for msg in lines if msg.decode("utf-8").startswith("commit")]
        assert len(commits) == 1

        # You should be able to combine depth and cloning a branch.
        # Otherwise with a depth of 1 you could clone the master
        # branch and then not be able to switch to the wanted branch,
        # because this branch would not be there: the revision that it
        # points to is not in the downloaded history.
        shutil.rmtree(src["egg"])
        tempdir["buildout.cfg"].create_file(
            "[buildout]",
            "mr.developer-threads = 1",
            "git-clone-depth = 1",
            "[sources]",
            "egg = git %s branch=test" % repository.url,
        )
        develop("co", "egg")

        # check that there is only one commit in history
        lines = egg_process.check_call("git log", echo=False)
        commits = [msg for msg in lines if msg.decode("utf-8").startswith("commit")]
        assert len(commits) == 1

        # Check that the expected files from the branch are there
        assert set(os.listdir(src["egg"])) == {".git", "foo", "foo2"}

    # -- history rewrites (rebase + force-push of the remote branch) ----------

    def _branchWorkingCopy(self, repository, src, strategy=None):
        from mr.developer.git import GitWorkingCopy

        options = {"update-strategy": strategy} if strategy else {}
        return GitWorkingCopy(
            Source(
                kind="git",
                name="egg",
                branch="test",
                url="%s" % repository.base,
                path=src["egg"],
                **options,
            )
        )

    def _rewriteBranch(self, repository, branch="test"):
        # Amend the tip of the branch. From a checkout that already has the
        # old tip this is indistinguishable from a rebase and force-push:
        # the branch is both ahead and behind its remote.
        repository("git checkout %s" % branch, echo=False)
        repository("git commit --amend -m rewritten --allow-empty", echo=False)

    def _head(self, path):
        lines = Process(cwd=path).check_call("git rev-parse HEAD", echo=False)
        return lines[0].decode("utf-8").strip()

    def testUpdateFfOnlyRefusesRewrittenBranch(self, mkgitrepo, src):
        from mr.developer.common import WCError

        repository = mkgitrepo("repository")
        self.createDefaultContent(repository)
        wc = self._branchWorkingCopy(repository, src, "ff-only")
        wc.checkout(submodules="never")
        before = self._head(src["egg"])

        self._rewriteBranch(repository)
        with pytest.raises(WCError) as exc:
            wc.update(submodules="never")
        message = str(exc.value)
        assert "diverged" in message
        assert "reset --hard" in message
        # The checkout is left exactly as it was: no merge, no conflict, no
        # half-finished state for the next run to trip over.
        assert self._head(src["egg"]) == before
        assert not os.path.exists(os.path.join(src["egg"], ".git", "MERGE_HEAD"))

        shutil.rmtree(src["egg"])

    def testUpdateResetFollowsRewrittenBranch(self, mkgitrepo, src):
        repository = mkgitrepo("repository")
        self.createDefaultContent(repository)
        wc = self._branchWorkingCopy(repository, src, "reset")
        wc.checkout(submodules="never")

        self._rewriteBranch(repository)
        wc.update(submodules="never")
        # The checkout now matches the rewritten branch exactly.
        remote_head = (
            Process(cwd=repository.base)
            .check_call("git rev-parse test", echo=False)[0]
            .decode("utf-8")
            .strip()
        )
        assert self._head(src["egg"]) == remote_head
        assert wc.status() == "clean"

        shutil.rmtree(src["egg"])

    def testUpdateMergeKeepsHistoricalBehaviour(self, mkgitrepo, src):
        repository = mkgitrepo("repository")
        self.createDefaultContent(repository)
        # No update-strategy given: the default stays 'merge'.
        wc = self._branchWorkingCopy(repository, src)
        wc.checkout(submodules="never")

        self._rewriteBranch(repository)
        wc.update(submodules="never")
        # As before: a merge commit, so the checkout keeps the commits the
        # rewrite removed and is now ahead of its remote.
        parents = (
            Process(cwd=src["egg"])
            .check_call("git rev-list --parents -n 1 HEAD", echo=False)[0]
            .decode("utf-8")
            .split()
        )
        assert len(parents) == 3, "expected a merge commit (two parents)"
        assert wc.status() == "ahead"

        shutil.rmtree(src["egg"])

    def testStatusReportsDivergedSeparatelyFromAhead(self, mkgitrepo, src):
        repository = mkgitrepo("repository")
        self.createDefaultContent(repository)
        wc = self._branchWorkingCopy(repository, src, "ff-only")
        wc.checkout(submodules="never")
        assert wc.status() == "clean"

        self._rewriteBranch(repository)
        Process(cwd=src["egg"]).check_call("git fetch", echo=False)
        # Not 'ahead': the branch is ahead *and* behind, which is exactly what
        # distinguishes a rewritten remote branch from local commits.
        assert wc.status() == "diverged"

        shutil.rmtree(src["egg"])

    def testUnknownUpdateStrategyIsRejected(self, mkgitrepo, src):
        repository = mkgitrepo("repository")
        self.createDefaultContent(repository)
        self._branchWorkingCopy(repository, src).checkout(submodules="never")
        wc = self._branchWorkingCopy(repository, src, "no-such-strategy")
        with pytest.raises(SystemExit):
            wc.update(submodules="never")

        shutil.rmtree(src["egg"])

    def _commitInCheckout(self, path, fname, content, msg):
        egg = Process(cwd=path)
        egg.check_call("git config user.email dev@example.com", echo=False)
        egg.check_call("git config user.name dev", echo=False)
        with open(os.path.join(path, fname), "w") as f:
            f.write(content)
        egg.check_call("git add %s" % fname, echo=False)
        egg.check_call("git commit -m %s" % msg, echo=False)

    def _subjects(self, path):
        return [
            line.decode("utf-8")
            for line in Process(cwd=path).check_call("git log --format=%s", echo=False)
        ]

    def testUpdateRebaseKeepsLocalWorkAndDropsSupersededCommits(self, mkgitrepo, src):
        repository = mkgitrepo("repository")
        self.createDefaultContent(repository)
        wc = self._branchWorkingCopy(repository, src, "rebase")
        wc.checkout(submodules="never")
        # Work the developer has made but not pushed.
        self._commitInCheckout(src["egg"], "mine", "mine", "mine")

        self._rewriteBranch(repository)
        wc.update(submodules="never")

        subjects = self._subjects(src["egg"])
        # The local work survived, and sits on top of the rewritten branch.
        assert subjects[0] == "mine"
        assert subjects[1] == "rewritten"
        # The pre-rewrite copy of that commit is gone instead of being kept
        # alongside its replacement.
        assert "foo2" not in subjects
        assert wc.status() == "ahead"

        shutil.rmtree(src["egg"])

    def testUpdateRebaseWithoutLocalWorkMatchesRemote(self, mkgitrepo, src):
        repository = mkgitrepo("repository")
        self.createDefaultContent(repository)
        wc = self._branchWorkingCopy(repository, src, "rebase")
        wc.checkout(submodules="never")

        self._rewriteBranch(repository)
        wc.update(submodules="never")

        # Nothing of the developer's own to keep, so the checkout ends up on
        # the rewritten branch exactly.
        assert wc.status() == "clean"
        assert self._subjects(src["egg"])[0] == "rewritten"

        shutil.rmtree(src["egg"])

    def testUpdateRebaseAbortsOnConflict(self, mkgitrepo, src):
        from mr.developer.common import WCError

        repository = mkgitrepo("repository")
        self.createDefaultContent(repository)
        wc = self._branchWorkingCopy(repository, src, "rebase")
        wc.checkout(submodules="never")
        # Local work on the same file the rewrite changes.
        self._commitInCheckout(src["egg"], "foo2", "mine", "mine")
        before = self._head(src["egg"])

        repository("git checkout test", echo=False)
        with open(os.path.join("%s" % repository.base, "foo2"), "w") as f:
            f.write("theirs")
        repository("git add foo2", echo=False)
        repository("git commit --amend -m rewritten --no-edit", echo=False)

        with pytest.raises(WCError) as exc:
            wc.update(submodules="never")
        assert "conflict" in str(exc.value)
        assert "aborted" in str(exc.value)
        # Nothing half-finished is left behind: no rebase in progress, no
        # conflict markers, and the checkout is where it was.
        assert not os.path.exists(os.path.join(src["egg"], ".git", "rebase-merge"))
        assert not os.path.exists(os.path.join(src["egg"], ".git", "rebase-apply"))
        assert self._head(src["egg"]) == before
        with open(os.path.join(src["egg"], "foo2")) as f:
            assert "<<<<<<<" not in f.read()

        shutil.rmtree(src["egg"])

    def testUpdateResetDiscardsLocalCommitsWithoutRemoteChanges(self, mkgitrepo, src):
        repository = mkgitrepo("repository")
        self.createDefaultContent(repository)
        wc = self._branchWorkingCopy(repository, src, "reset")
        wc.checkout(submodules="never")
        # A commit made straight in the checkout, with nothing new on the
        # remote: the checkout is ahead but not behind. An earlier version
        # worked out ahead/behind for every strategy at once and stopped when
        # there was nothing to pull in, so the commit `reset` exists to
        # discard survived a deploy.
        self._commitInCheckout(src["egg"], "hotfix", "hotfix", "hotfix")
        assert "hotfix" in self._subjects(src["egg"])

        wc.update(submodules="never")

        assert "hotfix" not in self._subjects(src["egg"])
        assert wc.status() == "clean"

        shutil.rmtree(src["egg"])

    def testUpdateRebaseFastForwardsWhenOnlyBehind(self, mkgitrepo, src):
        repository = mkgitrepo("repository")
        self.createDefaultContent(repository)
        wc = self._branchWorkingCopy(repository, src, "rebase")
        wc.checkout(submodules="never")
        # Nothing of our own, the remote branch simply moves on. `git rebase`
        # fast-forwards this by itself, which is why the strategy hands it the
        # whole job instead of working out ahead/behind first.
        repository("git checkout test", echo=False)
        repository.add_file("foo3")

        wc.update(submodules="never")

        assert self._subjects(src["egg"])[0] == "foo3"
        assert wc.status() == "clean"

        shutil.rmtree(src["egg"])
