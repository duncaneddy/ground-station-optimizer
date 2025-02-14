# Ground Station Optimizer

This repository provides an application for determining the optimal ground station provider and station provider for a 
given satellite mission. It contains the code and examples supporting the associated paper presented at the 2025 IEEE 
Aerospace Conference. You can read more about the problem definition and formulation in the [preprint paper](https://arxiv.org/abs/2410.16282).

Ground Station Optimizer helps satellite operators determine the optimal ground station provider and station provider for
a given satellite mission. The application solves the multi-objective optimization problem to determine the optimal 
set of locations to support a mission.

## Usage

The tool comes in three parts: the core optimization libraries, example scripts, and a streamlit application.
Any of these can be used to define and solve a problem.

### Examples

To aid users in understanding and using the optimization framework of the library we have provided four examples in 
the `examples/` folder. These examples are:

- `full_example.py`: A generic example demonstrating setting up a problem and applying many different constraints to the problem
- `max_data_opt.py`: A total data downlink maximization problem. Optimization is subject to maximum cost constraints.
- `min_cost_opt.py`: A formulation of the mission-cost minimization problem. Optimization is subject to minimum data constraints.
- `max_gap_opt.py`: A formulation of the maximum contact-gap minimization problem. Problem formulation is subject to minimum data downlink constraints.

These scripts can be copied and modified for your specific application.

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

<!-- ### Streamlit Application

> [!NOTE] The streamlit application and docker builds are currently works in progress and not  -->

## Installation

Currently, the repository can be installed as a local package. We would like to add docker support and the streamlit
application eventually.

### Local Installation

To install the application using a local Python environment, first clone the repository:

```bash
git clone https://github.com/sisl/ground-station-optimizer
cd gsopt
```

Then, create a new Python environment. It is strongly recommended to use a virtual environment to avoid conflicts with
other Python packages. 

#### Prerequisites

> [!NOTE]
> Note currently MacOS and Linux distributions are supported. The repository relies on upstream dependencies which do not support Windows.

Prior to using the repository you need to install an ILP solver. This project currently supports [Gurobi](https://www.gurobi.com/), [SCIP](https://scipopt.org/#scipoptsuite), [coin-or](https://www.coin-or.org/), and [GLPK](https://www.gnu.org/software/glpk/). Gurobi is the preferred solver that is more robust and performant, but requires a commercial license for non-academic users. SCIP, Coin-Or CBC, and GLPK are open-source solvers that can be used as a free alternative.

The preferred free solver is Coin-Or CBC. You install their branch-and-cut mixed integer programming solver (coin-or cbc) via the [installation instructions](https://github.com/coin-or/COIN-OR-OptimizationSuite?tab=readme-ov-file#installers). For MacOS and Ubuntu you can install it via

- MacOS:
  ```bash
  brew install cbc
  ```
- Ubuntu:
  ```bash
  sudo apt-get install  coinor-cbc coinor-libcbc-dev
  ```

Another performant free-solver is [SCIP](https://scipopt.org/#scipoptsuite) which can be dowloaded and installed [from their main website](https://scipopt.org/index.php#download). If following this installation method, make sure that the `scip` executable is in your path and can be found with `which scip`.

If using GLPK, you can install the GNU Linear Programming Kit (GLPK) via:

- MacOS:
  ```bash
  brew install glpk
  ```
- Ubuntu:
  ```bash
  sudo apt install glpk-utils libglpk-dev
  ```

> [!NOTE]
> It should be noted that the Gurobi solver is significantly faster and more robust than coin-or.
>
> Additionally, any problems that involve a maximum-gap objective or constraints will significantly increase the problem size of the optimization problems, likely beyond what coin-or can solve in a reasonable amount of time.

For some performance comparisons, solving the problem `./examples/max_data_opt.py` with each solver on an AMD Ryzen 9 7950X3D 16-Core Processor with 128GB of RAM, the following results were obtained:

| Problem           | Gurobi | SCIP    | Coin-OR | GLPK |
|-------------------|--------|---------|---------|------|
| `max_data_opt.py` | 1.03s  | 257.54s | 91.93s  | 1.5s |

#### uv

The recommended way to install and manage your python environment for this project is through [uv](https://docs.astral.sh/uv/). You can install uv along with its shell autocompletions by following the [installation instructions](https://docs.astral.sh/uv/getting-started/installation/).

After installing uv. First check the install python versions and install a specific version

```bash
uv python list # Show python environments
uv python install -p 3.12 # Install latest python 3.12 release
```

Create and activate a local virtual environment

```bash
uv venv -p 3.12
source .venv/bin/activate
```

Then instlal the project dependencies with

```bash
uv pip install -e .
```


#### Pyenv + Pyenv-vritualenv

Pyenv and Pyenv-virtualenv provide one mechanism of managing python environments. To install Pyenv follow the instructions [here](https://github.com/pyenv/pyenv?tab=readme-ov-file#installation), and to
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

You can then execute one of the examples out of the examples folder.

```bash
python examples/full_example.py
```

<!-- ### Docker

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
``` -->

## Citation & Acknowledgement

If data or software from this repository is used in a publication, please cite the associated paper:

```
@misc{eddy2024optimalgroundstationselection,
      title={Optimal Ground Station Selection for Low-Earth Orbiting Satellites}, 
      author={Duncan Eddy and Michelle Ho and Mykel J. Kochenderfer},
      year={2024},
      eprint={2410.16282},
      archivePrefix={arXiv},
      primaryClass={cs.NI},
      url={https://arxiv.org/abs/2410.16282}, 
}
```

If you incorporate this software engineering technique or system into your product, please include a 
clear and visible acknowledgement to the authors.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
