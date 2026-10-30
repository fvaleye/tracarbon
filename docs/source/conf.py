# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Path setup --------------------------------------------------------------

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
#
import os
import sys

import toml

sys.path.insert(0, os.path.abspath("../.."))


def get_release_version() -> str:
    """
    Get the release version from the pyproject.toml file

    :return:
    """
    pyproject = toml.load("../../pyproject.toml")
    return pyproject["project"]["version"]


# -- Project information -----------------------------------------------------

project = "tracarbon"
copyright = "2023-2026 Tracarbon contributors"
author = "Florian Valeye"
version = get_release_version()
release = version

# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = ["sphinx.ext.autodoc"]
autodoc_typehints = "description"
nitpicky = True
nitpick_ignore = [
    ("py:class", "datetime.datetime"),
    ("py:class", "datadog.threadstats.base.ThreadStats"),
    ("py:class", "threading.Event"),
    ("py:class", "prometheus_client.metrics.Gauge"),
    ("py:class", "kubernetes.client.api.custom_objects_api.CustomObjectsApi"),
    ("py:class", "ConfigDict"),
    ("py:class", "BaseModel"),
]

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = []


# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
html_theme = "pydata_sphinx_theme"
html_favicon = "../../logo-mark.svg"
html_baseurl = "https://fvaleye.github.io/tracarbon/documentation/"
html_theme_options = {
    "github_url": "https://github.com/fvaleye/tracarbon",
    "use_edit_page_button": True,
    "logo": {"image_light": "../../logo.svg", "image_dark": "../../logo-dark.svg"},
}
html_context = {
    "github_user": "fvaleye",
    "github_repo": "tracarbon",
    "github_version": "main",
    "doc_path": "docs/source",
}

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ["_static"]
