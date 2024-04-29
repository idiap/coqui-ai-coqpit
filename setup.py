#!/usr/bin/env python

import os

import setuptools.command.build_py
import setuptools.command.develop
from setuptools import find_packages, setup

cwd = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(cwd, "VERSION")) as fin:
    version = fin.read().strip()


class build_py(setuptools.command.build_py.build_py):  # pylint: disable=too-many-ancestors
    def run(self):
        self.create_version_file()
        setuptools.command.build_py.build_py.run(self)

    @staticmethod
    def create_version_file():
        print("-- Building version " + version)
        version_path = os.path.join(cwd, "version.py")
        with open(version_path, "w") as f:
            f.write("__version__ = '{}'\n".format(version))


class develop(setuptools.command.develop.develop):
    def run(self):
        build_py.create_version_file()
        setuptools.command.develop.develop.run(self)


with open("README.md", "r", encoding="utf-8") as readme_file:
    README = readme_file.read()


setup(
    name="coqpit",
    version=version,
    url="https://github.com/erogol/coqpit",
    author="Eren Gölge",
    author_email="egolge@coqui.ai",
    maintainer="Enno Hermann",
    maintainer_email="enno.hermann@gmail.com",
    description="Simple (maybe too simple), light-weight config management through python data-classes.",
    long_description=README,
    long_description_content_type="text/markdown",
    license="",
    include_package_data=True,
    packages=find_packages(include=["coqpit*"]),
    project_urls={
        "Tracker": "https://github.com/idiap/coqui-ai-coqpit/issues",
        "Repository": "https://github.com/idiap/coqui-ai-coqpit",
        "Discussions": "https://github.com/idiap/coqui-ai-coqpit/discussions",
    },
    cmdclass={
        "build_py": build_py,
        "develop": develop,
    },
    install_requires=[],
    python_requires=">=3.9.0",
    classifiers=[
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Operating System :: POSIX :: Linux",
        "Operating System :: MacOS",
        "Operating System :: Microsoft :: Windows",
    ],
    zip_safe=False,
)
