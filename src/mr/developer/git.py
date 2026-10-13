from mr.developer import common

import os
import re
import subprocess
import sys

logger = common.logger


class GitError(common.WCError):
    pass


class GitWorkingCopy(common.BaseWorkingCopy):
    """The git working copy.

    Now supports git 1.5 and 1.6+ in a single codebase.
    """

    # the file protocol setting is only for testing, as it circumvents security
    # measures of default git settings
    _always_allow_file_protocol = False

    # TODO: make this configurable? It might not make sense however, as we
    # should make master and a lot of other conventional stuff configurable
    _upstream_name = "origin"

    # How an existing checkout is brought in line with its remote branch.
    #
    # 'merge'   runs ``git merge`` (historical behaviour, still the default).
    #           It cannot express "the remote branch was rewritten": the merge
    #           either silently resurrects the commits the rewrite removed, or
    #           stops with a conflict and leaves the checkout mid-merge.
    # 'ff-only' only ever fast-forwards. A rewritten remote branch is reported
    #           as such, with the command to recover, and the checkout is left
    #           untouched.
    # 'rebase'  replays the local commits on top of the rewritten branch. git
    #           drops the ones already upstream, which is what the superseded
    #           pre-rewrite copies are, so only genuine local work is kept. On
    #           a conflict the rebase is aborted and nothing is changed.
    # 'reset'   makes the checkout match the remote branch exactly, discarding
    #           local commits. Meant for checkouts nobody edits by hand:
    #           deployment hosts, CI, build images.
    _update_strategies = ("merge", "ff-only", "rebase", "reset")

    # Working copy states that stop an update before it starts, so the user is
    # asked rather than surprised. They differ per strategy because each
    # strategy can absorb a different amount.
    _blocking_status = {
        "merge": ("ahead", "diverged", "dirty"),
        "ff-only": ("dirty",),
        "rebase": ("dirty",),
        "reset": ("dirty",),
    }

    def __init__(self, source):
        self.git_executable = common.which("git")
        if "rev" in source and "revision" in source:
            raise ValueError(
                "The source definition of '%s' contains "
                "duplicate revision options." % source["name"]
            )
        # 'rev' is canonical
        if "revision" in source:
            source["rev"] = source["revision"]
            del source["revision"]
        if "branch" in source and "rev" in source:
            logger.error(
                "Cannot specify both branch (%s) and rev/revision "
                "(%s) in source for %s",
                source["branch"],
                source["rev"],
                source["name"],
            )
            sys.exit(1)
        super().__init__(source)

    @common.memoize
    def git_version(self):
        cmd = self.run_git(["--version"])
        stdout, stderr = cmd.communicate()
        if cmd.returncode != 0:
            logger.error("Could not determine git version")
            logger.error(f"'git --version' output was:\n{stdout}\n{stderr}")
            sys.exit(1)

        m = re.search(r"git version (\d+)\.(\d+)(\.\d+)?(\.\d+)?", stdout)
        if m is None:
            logger.error("Unable to parse git version output")
            logger.error(f"'git --version' output was:\n{stdout}\n{stderr}")
            sys.exit(1)
        version = m.groups()

        if version[3] is not None:
            version = (
                int(version[0]),
                int(version[1]),
                int(version[2][1:]),
                int(version[3][1:]),
            )
        elif version[2] is not None:
            version = (int(version[0]), int(version[1]), int(version[2][1:]))
        else:
            version = (int(version[0]), int(version[1]))
        if version < (1, 5):
            logger.error(
                "Git version %s is unsupported, please upgrade",
                ".".join([str(v) for v in version]),
            )
            sys.exit(1)
        return version

    @property
    def _remote_branch_prefix(self):
        version = self.git_version()
        if version < (1, 6, 3):
            return self._upstream_name
        else:
            return "remotes/%s" % self._upstream_name

    def run_git(self, commands, **kwargs):
        commands.insert(0, self.git_executable)
        kwargs["stdout"] = subprocess.PIPE
        kwargs["stderr"] = subprocess.PIPE
        # This should ease things up when multiple processes are trying to send
        # back to the main one large chunks of output
        kwargs["bufsize"] = -1
        kwargs["universal_newlines"] = True
        return subprocess.Popen(commands, **kwargs)

    def git_update_strategy(self, **kwargs):
        """The update strategy for this source.

        A per-source ``update-strategy=`` wins over the buildout-wide
        ``update-strategy`` option, which defaults to the historical 'merge'.
        """
        strategy = self.source.get(
            "update-strategy", kwargs.get("update_strategy") or "merge"
        )
        if strategy not in self._update_strategies:
            logger.error(
                "Unknown value '%s' for update-strategy of '%s'. Use one of: %s.",
                strategy,
                self.source["name"],
                ", ".join(self._update_strategies),
            )
            sys.exit(1)
        return strategy

    def blocks_update(self, status, **kwargs):
        return status in self._blocking_status[self.git_update_strategy(**kwargs)]

    def git_ahead_behind(self, branch):
        """How far HEAD and the remote branch have drifted apart.

        Returns ``(ahead, behind)``: commits the checkout has that the remote
        branch does not, and the other way round. ``ahead and behind`` means
        the histories diverged, which is what a rebase and force-push of the
        remote branch looks like from here.
        """
        rbp = self._remote_branch_prefix
        cmd = self.run_git(
            ["rev-list", "--left-right", "--count", f"HEAD...{rbp}/{branch}"],
            cwd=self.source["path"],
        )
        stdout, stderr = cmd.communicate()
        if cmd.returncode != 0:
            raise GitError(
                f"'git rev-list' against '{self._upstream_name}/{branch}' failed.\n{stderr}"
            )
        ahead, behind = stdout.split()
        return int(ahead), int(behind)

    def git_merge_rbranch(
        self, stdout_in, stderr_in, accept_missing=False, strategy="merge"
    ):
        path = self.source["path"]
        branch = self.source.get("branch", "master")

        cmd = self.run_git(["branch", "-a"], cwd=path)
        stdout, stderr = cmd.communicate()
        if cmd.returncode != 0:
            raise GitError("'git branch -a' failed.\n%s" % stderr)
        stdout_in += stdout
        stderr_in += stderr
        if not re.search(r"^(\*| ) %s$" % re.escape(branch), stdout, re.M):
            # The branch is not local.  We should not have reached
            # this, unless no branch was specified and we guess wrong
            # that it should be master.
            if accept_missing:
                logger.info("No such branch %r", branch)
                return (stdout_in, stderr_in)
            else:
                logger.error("No such branch %r", branch)
                sys.exit(1)

        rbp = self._remote_branch_prefix
        rbranch = f"{rbp}/{branch}"
        name = self.source["name"]
        upstream = f"{self._upstream_name}/{branch}"

        # Dispatch on the strategy first, and let each block say for itself
        # what it does about local commits.
        if strategy == "merge":
            # The historical behaviour, unchanged. `update()` refuses a
            # checkout that is already ahead or diverged before we get here,
            # so in practice this runs on a fast-forward -- except when the
            # divergence only appeared in the fetch above, which is exactly
            # what a rewritten remote branch does.
            argv = ["merge", rbranch]
        elif strategy == "reset":
            # "Match the remote branch exactly" needs nothing worked out
            # first: reset unconditionally. It is a no-op when the checkout
            # already matches.
            ahead, _behind = self.git_ahead_behind(branch)
            if ahead:
                self.output(
                    (
                        logger.warning,
                        f"Resetting '{name}' to '{upstream}': "
                        f"{ahead} local commit(s) are being discarded.",
                    )
                )
            argv = ["reset", "--hard", rbranch]
        elif strategy == "rebase":
            # Hand the whole job to git. `git rebase` already fast-forwards a
            # checkout that is only behind, does nothing when it is already up
            # to date, and replays the local commits otherwise -- leaving out
            # the ones that are already upstream, because it compares the
            # patch rather than the commit id, and those are the superseded
            # copies the rewrite replaced.
            return self.git_rebase_onto(stdout_in, stderr_in, branch)
        else:
            # ff-only. The only strategy that needs the counts, and only so it
            # can say how far apart the two have drifted.
            ahead, behind = self.git_ahead_behind(branch)
            if ahead and behind:
                raise GitError(
                    f"The checkout of '{name}' at '{path}' has diverged from "
                    f"'{upstream}': {ahead} local commit(s) the remote branch "
                    f"does not have, {behind} remote commit(s) this checkout "
                    f"does not have.\n"
                    f"That is what '{branch}' being rebased and force-pushed "
                    f"looks like from here.\n"
                    f"To throw the local commits away and match the remote:\n"
                    f"    git -C {path} reset --hard {upstream}\n"
                    f"To keep them, replay them onto the rewritten branch:\n"
                    f"    git -C {path} rebase --onto {upstream} "
                    f"<old-base> {branch}\n"
                    f"Or let mr.developer do it: 'update-strategy = rebase' "
                    f"replays the local commits, 'update-strategy = reset' "
                    f"discards them."
                )
            argv = ["merge", "--ff-only", rbranch]
        cmd = self.run_git(argv, cwd=path)
        stdout, stderr = cmd.communicate()
        if cmd.returncode != 0:
            raise GitError(
                f"git {argv[0]} of remote branch '{upstream}' failed.\n{stderr}"
            )
        return (stdout_in + stdout, stderr_in + stderr)

    def git_rebase_onto(self, stdout_in, stderr_in, branch):
        """Replay whatever is only in this checkout on top of the remote branch."""
        path = self.source["path"]
        name = self.source["name"]
        rbranch = f"{self._remote_branch_prefix}/{branch}"
        upstream = f"{self._upstream_name}/{branch}"
        cmd = self.run_git(["rebase", rbranch], cwd=path)
        stdout, stderr = cmd.communicate()
        if cmd.returncode != 0:
            # Never leave a rebase half-finished. A checkout with conflict
            # markers in it and a detached HEAD is the damage this strategy
            # exists to avoid, not a smaller version of it.
            self.run_git(["rebase", "--abort"], cwd=path).communicate()
            raise GitError(
                f"Replaying the local commits of '{name}' at '{path}' onto "
                f"'{upstream}' hit a conflict. The rebase was aborted, so the "
                f"checkout is exactly as it was.\n"
                f"'{branch}' was rebased and force-pushed, and the local "
                f"commits conflict with the rewrite.\n"
                f"Replay them by hand and resolve the conflict:\n"
                f"    git -C {path} rebase {upstream}\n"
                f"Or discard them and take the remote branch as it is:\n"
                f"    git -C {path} reset --hard {upstream}\n"
                f"{stderr}"
            )
        return (stdout_in + stdout, stderr_in + stderr)

    def git_checkout(self, **kwargs):
        name = self.source["name"]
        path = self.source["path"]
        url = self.source["url"]
        if os.path.exists(path):
            self.output(
                (logger.info, "Skipped cloning of existing package '%s'." % name)
            )
            return
        msg = "Cloned '%s' with git" % name
        if "branch" in self.source:
            msg += " using branch '%s'" % self.source["branch"]
        msg += " from '%s'." % url
        self.output((logger.info, msg))
        args = ["clone", "--quiet"]
        if "depth" in self.source:
            args.extend(["--depth", self.source["depth"]])
        if "branch" in self.source:
            args.extend(["-b", self.source["branch"]])
        args.extend([url, path])
        cmd = self.run_git(args)
        stdout, stderr = cmd.communicate()
        if cmd.returncode != 0:
            raise GitError(f"git cloning of '{name}' failed.\n{stderr}")
        if "rev" in self.source:
            stdout, stderr = self.git_switch_branch(stdout, stderr)
        if "pushurl" in self.source:
            stdout, stderr = self.git_set_pushurl(stdout, stderr)

        update_git_submodules = self.source.get("submodules", kwargs["submodules"])
        if update_git_submodules in ["always", "checkout"]:
            stdout, stderr, initialized = self.git_init_submodules(stdout, stderr)
            # Update only new submodules that we just registered. this is for safety reasons
            # as git submodule update on modified submodules may cause code loss
            for submodule in initialized:
                stdout, stderr = self.git_update_submodules(
                    stdout, stderr, submodule=submodule
                )
                self.output(
                    (
                        logger.info,
                        f"Initialized '{name}' submodule at '{submodule}' with git.",
                    )
                )

        if kwargs.get("verbose", False):
            return stdout

    def git_switch_branch(self, stdout_in, stderr_in, accept_missing=False):
        """Switch branches.

        If accept_missing is True, we do not switch the branch if it
        is not there.  Useful for switching back to master.
        """
        path = self.source["path"]
        branch = self.source.get("branch", "master")
        rbp = self._remote_branch_prefix
        cmd = self.run_git(["branch", "-a"], cwd=path)
        stdout, stderr = cmd.communicate()
        if cmd.returncode != 0:
            raise GitError("'git branch -a' failed.\n%s" % stderr)
        stdout_in += stdout
        stderr_in += stderr
        if "rev" in self.source:
            # A tag or revision was specified instead of a branch
            argv = ["checkout", self.source["rev"]]
            self.output((logger.info, "Switching to rev '%s'." % self.source["rev"]))
        elif re.search(r"^(\*| ) %s$" % re.escape(branch), stdout, re.M):
            # the branch is local, normal checkout will work
            argv = ["checkout", branch]
            self.output((logger.info, "Switching to branch '%s'." % branch))
        elif re.search(
            "^  " + re.escape(rbp) + r"\/" + re.escape(branch) + "$", stdout, re.M
        ):
            # the branch is not local, normal checkout won't work here
            rbranch = f"{rbp}/{branch}"
            argv = ["checkout", "-b", branch, rbranch]
            self.output((logger.info, "Switching to remote branch '%s'." % rbranch))
        elif accept_missing:
            self.output((logger.info, "No such branch %r", branch))
            return (stdout_in + stdout, stderr_in + stderr)
        else:
            self.output((logger.error, "No such branch %r", branch))
            sys.exit(1)
        # Moving off a branch the developer is working on is silent otherwise:
        # the commits are safe, but the build, the develop-egg and the tests
        # quietly use the configured branch instead. Say so.
        if argv[0] == "checkout" and len(argv) == 2:
            current = (
                self.run_git(["symbolic-ref", "--short", "-q", "HEAD"], cwd=path)
                .communicate()[0]
                .strip()
            )
            if current and current != argv[1]:
                self.output(
                    (
                        logger.warning,
                        f"Switching '{self.source['name']}' from branch "
                        f"'{current}' to '{argv[1]}' as configured in "
                        f"[sources]. Commits on '{current}' are kept, but are "
                        f"not what gets built.",
                    )
                )
        # runs the checkout with predetermined arguments
        cmd = self.run_git(argv, cwd=path)
        stdout, stderr = cmd.communicate()
        if cmd.returncode != 0:
            # Name what was actually asked for. With a 'rev' the branch is
            # irrelevant, and reporting the default 'master' sends people
            # looking for a branch that was never involved.
            wanted = (
                f"rev '{self.source['rev']}'"
                if "rev" in self.source
                else f"branch '{branch}'"
            )
            raise GitError(f"git checkout of {wanted} failed.\n{stderr}")
        return (stdout_in + stdout, stderr_in + stderr)

    def git_update(self, **kwargs):
        name = self.source["name"]
        path = self.source["path"]
        self.output((logger.info, "Updated '%s' with git." % name))
        # First we fetch.  This should always be possible.
        argv = ["fetch"]
        cmd = self.run_git(argv, cwd=path)
        stdout, stderr = cmd.communicate()
        if cmd.returncode != 0:
            raise GitError(f"git fetch of '{name}' failed.\n{stderr}")
        strategy = self.git_update_strategy(**kwargs)
        if "rev" in self.source:
            stdout, stderr = self.git_switch_branch(stdout, stderr)
        elif "branch" in self.source:
            stdout, stderr = self.git_switch_branch(stdout, stderr)
            stdout, stderr = self.git_merge_rbranch(stdout, stderr, strategy=strategy)
        else:
            # We may have specified a branch previously but not
            # anymore.  In that case, we want to revert to master.
            stdout, stderr = self.git_switch_branch(stdout, stderr, accept_missing=True)
            stdout, stderr = self.git_merge_rbranch(
                stdout, stderr, accept_missing=True, strategy=strategy
            )

        update_git_submodules = self.source.get("submodules", kwargs["submodules"])
        if update_git_submodules in ["always"]:
            stdout, stderr, initialized = self.git_init_submodules(stdout, stderr)
            # Update only new submodules that we just registered. this is for safety reasons
            # as git submodule update on modified subomdules may cause code loss
            for submodule in initialized:
                stdout, stderr = self.git_update_submodules(
                    stdout, stderr, submodule=submodule
                )
                self.output(
                    (
                        logger.info,
                        f"Initialized '{name}' submodule at '{submodule}' with git.",
                    )
                )

        if kwargs.get("verbose", False):
            return stdout

    def checkout(self, **kwargs):
        name = self.source["name"]
        path = self.source["path"]
        update = self.should_update(**kwargs)
        if os.path.exists(path):
            if update:
                return self.update(**kwargs)
            elif self.matches():
                self.output(
                    (logger.info, "Skipped checkout of existing package '%s'." % name)
                )
            else:
                self.output(
                    (
                        logger.warning,
                        "Checkout URL for existing package '{}' differs. Expected '{}'.".format(
                            name, self.source["url"]
                        ),
                    )
                )
        else:
            return self.git_checkout(**kwargs)

    def status(self, **kwargs):
        path = self.source["path"]
        cmd = self.run_git(["status", "-s", "-b"], cwd=path)
        stdout, stderr = cmd.communicate()
        lines = stdout.strip().split("\n")
        if len(lines) == 1:
            # The branch line of ``git status -s -b`` reads e.g.
            # ``## main...origin/main [ahead 2, behind 3]``. Reporting that as
            # plain "ahead" loses exactly the case we care about: a remote
            # branch that was rewritten leaves the checkout both ahead and
            # behind.
            ahead = "ahead" in lines[0]
            behind = "behind" in lines[0]
            if ahead and behind:
                status = "diverged"
            elif ahead:
                status = "ahead"
            elif behind:
                status = "behind"
            else:
                status = "clean"
        else:
            status = "dirty"
        if kwargs.get("verbose", False):
            return status, stdout
        else:
            return status

    def matches(self):
        name = self.source["name"]
        path = self.source["path"]
        # This is the old matching code: it does not work on 1.5 due to the
        # lack of the -v switch
        cmd = self.run_git(["remote", "show", "-n", self._upstream_name], cwd=path)
        stdout, stderr = cmd.communicate()
        if cmd.returncode != 0:
            raise GitError(f"git remote of '{name}' failed.\n{stderr}")
        return self.source["url"] in stdout.split()

    def update(self, **kwargs):
        name = self.source["name"]
        if not self.matches():
            self.output(
                (
                    logger.warning,
                    "Can't update package '%s' because its URL doesn't match." % name,
                )
            )
        strategy = self.git_update_strategy(**kwargs)
        status = self.status()
        if status in self._blocking_status[strategy] and not kwargs.get("force", False):
            if status == "dirty":
                raise GitError("Can't update package '%s' because it's dirty." % name)
            raise GitError(
                f"Can't update package '{name}' because its branch has "
                f"{status} from the remote one (the working tree itself is "
                f"clean). Commit or discard the local commits, or set "
                f"'update-strategy = ff-only' for a precise report and "
                f"'reset' to let mr.developer discard them."
            )
        return self.git_update(**kwargs)

    def git_set_pushurl(self, stdout_in, stderr_in):
        cmd = self.run_git(
            [
                "config",
                "remote.%s.pushurl" % self._upstream_name,
                self.source["pushurl"],
            ],
            cwd=self.source["path"],
        )
        stdout, stderr = cmd.communicate()

        if cmd.returncode != 0:
            raise GitError(
                "git config remote.{}.pushurl {} \nfailed.\n".format(
                    self._upstream_name, self.source["pushurl"]
                )
            )
        return (stdout_in + stdout, stderr_in + stderr)

    def git_init_submodules(self, stdout_in, stderr_in):
        cmd = self.run_git(["submodule", "init"], cwd=self.source["path"])
        stdout, stderr = cmd.communicate()
        if cmd.returncode != 0:
            raise GitError("git submodule init failed.\n")
        output = stdout
        if not output:
            output = stderr
        initialized_submodules = re.findall(r'\s+[\'"](.*?)[\'"]\s+\(.+\)', output)
        return (stdout_in + stdout, stderr_in + stderr, initialized_submodules)

    def git_update_submodules(self, stdout_in, stderr_in, submodule="all"):
        params = ["submodule", "update"]
        if self._always_allow_file_protocol:
            params[0:0] = ["-c", "protocol.file.allow=always"]
        if submodule != "all":
            params.append(submodule)
        cmd = self.run_git(params, cwd=self.source["path"])
        stdout, stderr = cmd.communicate()
        if cmd.returncode != 0:
            raise GitError("git submodule update failed.\n")
        return (stdout_in + stdout, stderr_in + stderr)
