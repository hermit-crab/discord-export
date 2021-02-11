#!/bin/python
from os.path import join, dirname
from setuptools import setup, find_packages


with open(join(dirname(__file__), 'discord_export/VERSION')) as f:
    version = f.read().strip()


setup(
    name='discord-export',
    version=version,
    packages=find_packages(),
    install_requires=[
        'dateparser',
        'aioconsole',
        'aiohttp',
        'tqdm',
    ],
    entry_points={
        'console_scripts': [
            'discord-export = discord_export:cli',
        ]
    },
)
