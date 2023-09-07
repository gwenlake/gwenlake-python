# coding: utf-8

from setuptools import setup, find_packages

setup(
    name="gwenlake",
    version='0.1.0',
    url="https://github.com/gwenlake/gwenlake-python",
    author="The Gwenlake Team",
    author_email="info@gwenlake.com",
    install_requires=["requests", "pandas"],
    packages=find_packages(exclude=('tests'))
)
