#!/usr/bin/env python3
"""Setup script for auth daemon."""

from setuptools import setup, find_packages

setup(
    name="auth-daemon",
    version="0.1.0",
    description="Multi-service OAuth/device-flow automation daemon for macOS",
    author="Auth Daemon Contributors",
    python_requires=">=3.8",
    py_modules=["auth_daemon", "auth_cli", "auth_services"],
    entry_points={
        "console_scripts": [
            "auth-cli=auth_cli:main",
            "auth-daemon=auth_daemon:main",
        ],
    },
    install_requires=[
        "requests>=2.28.0",
    ],
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Environment :: Console",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: MacOS",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
)
