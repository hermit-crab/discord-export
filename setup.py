#!/bin/python
from setuptools import setup, find_packages


with open('discord_export/__init__.py') as f:
    exec(f.read())


setup(
    name='discord-export',
    version=__version__,
    packages=find_packages(),
    install_requires=[
        'logzero',
        'colorama',
        'aioconsole',
        'discord.py>=1.0.0a',
    ],
    dependency_links=[
        "git+https://github.com/Rapptz/discord.py.git@rewrite#egg=discord.py-1.0.0a"
    ],
    entry_points={
        'console_scripts': [
            'discord-export = discord_export.__main__:main',
        ]
    },
)
