import json
import datetime
import typer
from typing_extensions import Annotated
from enum  import Enum
from pathlib import Path

import brahe as bh

from gsopt import utils
from gsopt.ephemeris import get_tles
from gsopt.models import OptimizationWindow
from gsopt.milp_optimizer import MilpGSOptimizer
from gsopt.utils import satellites_from_constellation_str, ground_stations_from_geojson

app = typer.Typer(no_args_is_help=True)

# TODO: This should auto-update data if stale
bh.EOP.load("data/iau2000A_finals_ab.txt")

# Suppress warnings
utils.filter_warnings()

class Providers(str, Enum):
    Azure = "Azure"
    Leaf = "Leaf"
    Atlas = "Atlas"
    Viasat = "Viasat"


@app.command()
def milp(
        provider: Annotated[list[Providers], typer.Option(help="Default Ground Station Provider")] = None,
        provider_file: Annotated[Path, typer.Option(help="Path to ground station GeoJSON file")] = None,
        constellation: Annotated[list[str], typer.Option(help="Constellation Name")] = None,
        sim_duration: Annotated[int, typer.Option(help="Simulation Duration in days")] = 7,
):
    # Validate inputs
    if not provider_file and not provider:
        typer.echo("Please provide a provider or a provider file", err=True)

    if not constellation:
        pass

    if sim_duration < 1:
        typer.echo("Simulation duration must be greater than or equal to 1", err=True)

    # Load Stations

    stations = []

    for p in provider:
        stations.extend(ground_stations_from_geojson(json.load(open(f'./data/groundstations/{p.lower()}.json', 'r'))))

    if provider_file:
        stations.extend(ground_stations_from_geojson(json.load(open(provider_file, 'r'))))

    typer.echo(f'Loaded {len(stations)} ground stations')

    # Load Spacecraft

    spacecraft = []

    tles = get_tles()

    for c in constellation:
        # Convert input into upper case to match stored data format
        spacecraft.extend(satellites_from_constellation_str(c.upper(), tles))

    typer.echo(f'Loaded {len(spacecraft)} spacecraft')

    # Set optimization window
    t_start = datetime.datetime.now()
    t_end   = t_start + datetime.timedelta(days=sim_duration)
    opt_window = OptimizationWindow(
        opt_start=t_start,
        opt_end=t_end,
        sim_start=t_start,
        sim_end=t_end
    )

    # Define Optimization problem
    gsopt = MilpGSOptimizer(
        opt_window=opt_window,
        stations=stations,
        satellites=spacecraft,
    )

    # Compute Contacts
    typer.echo("Computing Contacts...")
    gsopt.compute_contacts()
    typer.echo(f"Contact computation complete. Found {len(gsopt.contacts)} contacts in {gsopt.contact_compute_time:.2f} seconds")

    # Define optimization problem
    gsopt.set_objective_maximize_contact_time()

    typer.echo("Solving Optimization Problem...")
    gsopt.solve()
    typer.echo(f"Optimization complete. Total contact time: {gsopt.solve_time:.2f} seconds")

    for c in gsopt.contacts:
        typer.echo(f"Contact <Sc:{c.spacecraft_id},Station:{c.name},Provider:{c.provider}> | Duration: {c.t_duration:.2f} seconds - {gsopt.contact_nodes[c.id].value}")

    typer.echo(f"Total Objective value: {gsopt.objective.expr()}")

def main():
    app()
