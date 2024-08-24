# Ground Station Optimizer

This repository provides an application for determining the optimal ground station provider and station provider for a 
given satellite mission. It contains the code and examples supporting the associated paper presented at the 2025 IEEE 
Aerospace Conference.

Ground Station Optimizer helps satellite operators determine the optimal ground station provider and station provider for
a given satellite mission. The application solves the multi-objective optimization problem to determine the optimal 
set of locations to support a mission.

## Usage

The tool comes in three parts: the core optimization libraries, a command-line interface, and a streamlit application.
Any of these can be used to define and solve a problem.

### Python Library

To write

### Streamlit Application

To write

### Command Line Interface

To write

## Local Installation

There are two installation options: using a local Python environment or using Docker. The Docker option is recommended
for ease of installation and use for most users that want to use the application. The Python environment option is
recommended for developers that want to modify the application.

### Docker

The application can be run using Docker. To do so, first install Docker on your system by following the instructions
[here](https://docs.docker.com/get-docker/). Then, run the following command to start the application:

```bash
docker-compose up --detach
```

The application will be available at [http://localhost:8080](http://localhost:8080).

To stop the application, run the following

```bash
docker-compose down
```

If the application is not updating you may need to remove the Docker image and rebuild it:

```bash
docker-compose down
docker rm $(docker ps -aq)     # Note: This will remove all Docker containers
docker rmi $(docker images -q) # Note: This will remove all Docker images
docker-compose up --detach
```

### Python Environment

To install the application using a local Python environment, first clone the repository:

```bash
git clone https://github.com/sisl/ground-station-optimizer
cd gsopt
```

Then, create a new Python environment. It is strongly recommended to use a virtual environment to avoid conflicts with
other Python packages. Pyenv and Pyenv-virtualenv are recommended for managing Python versions and virtual environments.

To install Pyenv follow the instructions [here](https://github.com/pyenv/pyenv?tab=readme-ov-file#installation), and to
install Pyenv-virtualenv follow the instructions [here](https://github.com/pyenv/pyenv-virtualenv?tab=readme-ov-file#installation).

Once Pyenv and Pyenv-virtualenv are installed, create a new Python environment and install the required packages:

```bash
pyenv install 3.11.9
```

Next, create a new virtual environment:

```bash
pyenv virtualenv 3.11.9 gsopt
```

Finally set the local Python version to the new virtual environment:

```bash
pyenv local gsopt
```

Now, install the required packages:

```bash
pip install -e .
```

The application can now be run using the following command:

```bash
streamlit run ./gsopt/app.py
```

## Citation & Acknowledgement

If data or software from this repository is used in a publication, please cite the associated paper:

```
TODO
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
