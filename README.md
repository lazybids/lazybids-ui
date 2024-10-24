# LazyBIDS-UI

LazyBIDS-UI is a web-based user interface for interacting with BIDS datasets. It provides a visual and intuitive way to explore, manage, and analyze BIDS-compliant neuroimaging data, leveraging the power of [LazyBIDS](https://github.com/lazybids/lazybids) as its core io-library.

Furthermore, LazyBIDS-UI's [REST-API](https://lazybids.github.io/lazybids-ui/scalar) provides an easy way to interact with datasets on the server, and download only the parts you need, when you need them. The [LazyBIDS](https://github.com/lazybids/lazybids) library showcases how a remote dataset can be accessed in the same way you would access a local dataset.

Finally, LazyBIDS-UI is almost fully written in Python, and aims to keep things simple. Making it easy to modify LazyBIDS-UI to your specific needs. The combination of [jinja](https://jinja.palletsprojects.com/en/3.1.x/) html templates, with [htmx](https://htmx.org) for interactions keeps things simple, responsive and extensability.  
Because all assets are availble both in html and throught the [REST-API](https://lazybids.github.io/lazybids-ui/scalar), extensions can even be implemented in frontend frameworks like Angular, React or Vue. Simply:  
- Create an [htmx](https://htmx.org) enabled div where you'd like your plugin to appear
- Link to your frontend with the right url/parameters
- Query the API for the data you need
- Voilà.

Install the latest version:
```bash
pip install lazybids-ui
```

## Features

- **Visual Dataset Explorer**: Easily navigate through subjects, sessions, and scans with an intuitive interface.
- **Interactive Data Viewer**: View and interact with neuroimaging data directly in your browser.
- **Metadata Management**: Explore and edit metadata associated with your BIDS datasets.
- **RESTful API**: Programmatically interact with your datasets using a comprehensive API.
- **Integration with LazyBIDS**: Seamlessly work with LazyBIDS objects and functionality.

## Documentation

For detailed documentation, including API specifications and advanced usage, please visit our [GitHub Pages](https://lazybids.github.io/lazybids-ui/).

## Quick Start

1. Install LazyBIDS-UI:
   ```bash
   pip install lazybids-ui
   ```

2. Start the LazyBIDS-UI server:
   ```bash
   lazybids-ui start
   ```

3. Open your web browser and navigate to `http://localhost:8000` to access the LazyBIDS-UI interface.

## Screenshots

[Space for screenshots/GIFs of the UI]

## REST API

LazyBIDS-UI provides a comprehensive REST API for programmatic interaction with your BIDS datasets. For full API documentation, please refer to our [API Specifications](https://lazybids.github.io/lazybids-ui/api-docs).

Example usage:
```python
import requests

# Get all datasets
response = requests.get('http://localhost:8000/api/datasets')
datasets = response.json()

# Get details of a specific dataset
dataset_id = datasets[0]['id']
response = requests.get(f'http://localhost:8000/api/dataset/{dataset_id}')
dataset_details = response.json()
```

## Contributing

We welcome contributions to LazyBIDS-UI! Please see our [Contributing Guidelines](CONTRIBUTING.md) for more information on how to get started.

## License

LazyBIDS-UI is released under the [Apache 2 License](LICENSE).

## Acknowledgements

LazyBIDS-UI is built upon the excellent [LazyBIDS](https://github.com/lazybids/lazybids) library and is inspired by the BIDS standard and community.

