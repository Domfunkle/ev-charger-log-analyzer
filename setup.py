#!/usr/bin/env python3
"""
Setup script for EV Charger Log Analyzer
"""

from setuptools import setup, find_packages
from pathlib import Path

# Read the README for long description
readme_file = Path(__file__).parent / "README.md"
long_description = readme_file.read_text(encoding='utf-8') if readme_file.exists() else ""

setup(
    name="ev-charger-log-analyzer",
    version="0.0.4",
    author="Daniel Nathanson",
    description="Automated analysis tool for EV charger logs",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/Domfunkle/ev-charger-log-analyzer",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: System :: Logging",
        "Topic :: Utilities",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.6",
    install_requires=[
        "rich>=13.0.0",         # Modern terminal UI with colors, tables, progress bars
        "pandas>=1.3.0",        # Data analysis and CSV export
        "python-dateutil>=2.8.0",  # Advanced timestamp parsing
    ],
    entry_points={
        'console_scripts': [
            'delta-ac-max-analyzer=analyzers.delta_ac_max.analyze:main',
        ],
    },
    include_package_data=True,
    zip_safe=False,
)
