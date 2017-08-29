# -*- coding: utf-8 -*-

from setuptools import setup, find_packages


with open('README.rst') as f:
    readme = f.read()

with open('LICENSE') as f:
    license = f.read()

setup(
    name='gitplot',
    version='0.1.0',
    description='git repo graphical plotter',
    long_description=readme,
    author='Robert Cronk',
    author_email='cronk.r@gmail.com',
    url='https://github.com/rcronk/gitplot',
    license=license,
    packages=find_packages(exclude=('tests', 'docs'))
)
