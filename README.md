# Ground Station Optimizer

This repository provides an application for determining the optimal ground station provider and station provider for a 
given satellite mission. It contains the code and examples supporting the associated paper presented at the 2025 IEEE 
Aerospace Conference. You can read more about the problem definition and formulation in the pre-print available here
(to be updated).

Ground Station Optimizer helps satellite operators determine the optimal ground station provider and station provider for
a given satellite mission. The application solves the multi-objective optimization problem to determine the optimal 
set of locations to support a mission.

## Usage

The tool comes in three parts: the core optimization libraries, example scripts, and a streamlit application.
Any of these can be used to define and solve a problem.

### Python Library

The optimization library is structured as follows:

```bash
./gsopt
├── analysis.py           # Helper scripts for analyzing simulation outputs
├── app.py                # Main entry point for streamlit application
├── ephemeris.py          # Functions for fetching, storing, and loading satellite ephemeris
├── logging.py            # Logging utilities and configuration
├── milp_constraints.py   # Constraint definition
├── milp_core.py          # Core data models for IP formulation
├── milp_objectives.py    # Objective definition
├── milp_optimizer.py     # IP optimizer class definition
├── models.py             # Common data models for problem modeling
├── optimizer.py          # Base optimizer class
├── plots.py              # Plotting utilities
├── scenarios.py          # Simulation scenario definition and generation tools
├── sim_analysis.py       # Additional helper functions for simulation analysis
├── utils.py              # Misc. utilities
└── widgets.py            # Streamlit widgets for application definition
```

For most script based applciations users will want to add new constraints or objectives in `milp_constraint.py` or
`milp_objectives.py` respectively. In rare cases where more core constraints must be added that is done in the 
`milp_optimizer.py` file. The `scenarios.py` file provides utilities to enable users to define new randomized scenarios
for evaluation.

### Examples

To aid users in understanding and using the optimization framework of the library we have provided four examples in 
the `examples/` folder. These examples are:

- `full_example.py`: A generic example demonstrating setting up a problem and applying many different constraints to the problem
- `max_data_opt.py`: A total data downlink maximization problem. Optimization is subject to maximum cost constraints.
- `min_cost_opt.py`: A formulation of the mission-cost minimization problem. Optimization is subject to minimum data constraints.
- `max_gap_opt.py`: A formulation of the maximum contact-gap minimization problem. Problem formulation is subject to minimum data downlink constraints.

### Streamlit Application

**WORK IN PROGRESS** _The streamlit application is currently in the process of being updated_ 

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
To be updated once available
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
