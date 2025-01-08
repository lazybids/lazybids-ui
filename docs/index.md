# LazyBIDS-UI Documentation

LazyBIDS-UI is a web-based interface for managing and interacting with BIDS (Brain Imaging Data Structure) datasets. It provides a user-friendly way to explore, analyze, and share neuroimaging data while leveraging the power of the LazyBIDS library.

## Table of Contents

1. [Introduction](#introduction)
2. [Getting Started](#getting-started)
3. [User Interface](#user-interface)
4. [Features](#features)
5. [LazyBIDS Library](#lazybids-library)
6. [REST API](#rest-api)
7. [Troubleshooting](#troubleshooting)
8. [Contributing](#contributing)

## Introduction

LazyBIDS-UI is designed to simplify the process of working with BIDS datasets. It provides a web interface that allows users to:

- Browse and explore BIDS datasets in a graphical user interface
- View and analyze neuroimaging data
- Manage datasets, subjects, sessions, and scans
- Interact with BIDS datasets using REST-API or [LazyBIDS](https://lazybids.github.io/lazybids) python library

## Getting Started

Install and run the latest version:

```bash
git clone https://github.com/lazybids/lazyBIDS-ui.git
cd ./lazyBIDS-ui
pip install .
cd ./lazybids_ui/
fastapi run
```

## User Interface
<iframe width="560" height="315" src="https://www.youtube.com/embed/VM2L-RWl9eI" title="LazyBIDS-UI Demo" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>


## Features

- Dataset Management
- Subject and Session Overview
- Scan Visualization
- Metadata Exploration
- Search Functionality
- Data Export

### Dataset Managment
LazyBIDS-UI provides multiple ways to add datasets to the system:

**Upload ZIP File**  
   * Upload a compressed BIDS dataset directly through the web interface
   * Supports ZIP files containing complete BIDS-compliant datasets
   * Automatically extracts and validates the dataset structure

**Local Directory**  
   * Point to an existing BIDS dataset directory on the server
   * Useful for large datasets already present on the system
   * Supports both absolute and relative paths
   * No data copying required - works directly with the source files

**OpenNeuro Integration**  
   * Download datasets directly from OpenNeuro.org
   * Simply provide the OpenNeuro dataset ID (e.g., ds000001)
   * Automatically downloads and imports the complete dataset
   * Maintains all original metadata and file organization

After import, datasets are immediately available for browsing, visualization, and analysis through the UI.


## LazyBIDS Library

LazyBIDS-UI is built on top of the LazyBIDS library, which provides powerful tools for working with BIDS datasets programmatically. For detailed information about the LazyBIDS library and its Python client to interact with datasets on the server, please visit:

[LazyBIDS Documentation](https://lazybids.github.io/lazybids/)

## REST API

LazyBIDS-UI exposes a REST API that allows programmatic access to BIDS datasets. This API can be used to integrate LazyBIDS-UI with other tools and workflows.

For detailed API documentation, including endpoints, request/response formats, and examples in various programming languages, please refer to:

[LazyBIDS-UI API Reference](https://lazybids.github.io/lazybids-ui/scalar)


## Contributing

We welcome contributions to LazyBIDS-UI! If you'd like to report a bug, suggest a feature, or contribute code, please visit our GitHub repository:

[LazyBIDS-UI on GitHub](https://github.com/lazybids/lazybids-ui)
