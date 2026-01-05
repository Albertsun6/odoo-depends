"""
Setup script for Odoo Module Dependency Analyzer
"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as f:
    long_description = f.read()

setup(
    name="odoo-depends",
    version="1.0.0",
    author="Galaxy",
    author_email="galaxy@example.com",
    description="Odoo模块依赖分析器 - 分析、可视化Odoo模块依赖关系",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/galaxy/odoo-depends",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: Console",
        "Environment :: Web Environment",
        "Framework :: Flask",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: System :: Software Distribution",
    ],
    python_requires=">=3.9",
    install_requires=[
        "flask>=3.0.0",
        "networkx>=3.2",
        "click>=8.1.0",
        "pyvis>=0.3.2",
    ],
    extras_require={
        "dev": [
            "black>=24.0.0",
            "flake8>=7.0.0",
            "pytest>=8.0.0",
        ],
        "graphviz": [
            "graphviz>=0.20",
            "pydot>=2.0.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "odoo-depends=odoo_depends.cli:main",
        ],
    },
    include_package_data=True,
    zip_safe=False,
)
