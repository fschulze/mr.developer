from setuptools import setup


setup(
    name='mr.developer.addon',
    version=0.1,
    packages=['mr'],
    entry_points="""
    [mr.developer.workingcopytypes]
    svn = mr.developer.addon:SVNWorkingCopy""")
