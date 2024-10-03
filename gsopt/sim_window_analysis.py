import json
import matplotlib.pyplot as plt
from sim_analysis import load_solution, compute_contact_gaps, compute_gap_statistics, compute_contact_statistics

# Update rcParams for LaTeX style plots and increased axes font size
plt.rcParams.update({
    "text.usetex": True,
    "font.family": "serif",
    "font.serif": ["Computer Modern"],
    "text.latex.preamble": r"""
        \usepackage{amsmath}
        \usepackage{siunitx}
    """,
    "axes.labelsize": 14,
    "font.size": 14,
    "xtick.labelsize": 14,
    "ytick.labelsize": 14
})

# Updated list of files representing each optimization window
files = [
    'gsopt/contact_analysis/2024_09_17T19_11_12/contact_analysis.py_sats_100_days_1.json',
    'gsopt/contact_analysis/2024_09_17T19_11_12/contact_analysis.py_sats_100_days_2.json',
    'gsopt/contact_analysis/2024_09_17T06_06_01/contact_analysis.py_sats_100_days_3.json',
    'gsopt/contact_analysis/2024_09_17T19_11_12/contact_analysis.py_sats_100_days_5.json',
    'gsopt/contact_analysis/2024_09_17T06_06_01/contact_analysis.py_sats_100_days_7.json',
    'gsopt/contact_analysis/2024_09_17T19_11_12/contact_analysis.py_sats_100_days_10.json',
    'gsopt/contact_analysis/2024_09_17T19_11_12/contact_analysis.py_sats_100_days_20.json',
    'gsopt/contact_analysis/2024_09_17T19_11_12/contact_analysis.py_sats_100_days_30.json',
    'gsopt/contact_analysis/2024_09_17T19_11_12/contact_analysis.py_sats_100_days_50.json',
    'gsopt/contact_analysis/2024_09_17T06_06_01/contact_analysis.py_sats_100_days_60.json',
    'gsopt/contact_analysis/2024_09_17T06_06_01/contact_analysis.py_sats_100_days_90.json',
    'gsopt/contact_analysis/2024_09_17T19_11_12/contact_analysis.py_sats_100_days_100.json',
    'gsopt/contact_analysis/2024_09_17T19_11_12/contact_analysis.py_sats_100_days_180.json'
]

optimization_days = [1, 2, 3, 5, 7, 10, 20, 30, 50, 60, 90, 100, 180]

# Initialize lists to store metrics
mean_contacts_per_day_per_sat_list = []
mean_contact_duration_list = []
mean_gap_duration_list = []

for i, file in enumerate(files):
    print(f"Processing file: {file}")  # Print statement to indicate which file is being processed

    # Load the data from the file
    with open(file, 'r') as f:
        data = json.load(f)

    # Load the solution
    solution = load_solution(data)

    # Extract contacts
    contacts = list(solution.contact_dict.values())

    # Compute contact statistics
    contact_stats = compute_contact_statistics(contacts)

    # Calculate the average number of contacts per day per satellite
    num_contacts = contact_stats['num_contacts']
    num_satellites = len(solution.satellite_dict)
    mean_contacts_per_day_per_sat = num_contacts / (optimization_days[i] * num_satellites)
    mean_contacts_per_day_per_sat_list.append(mean_contacts_per_day_per_sat)

    # Store the mean contact duration
    mean_contact_duration_list.append(contact_stats['mean_duration_s'])

    # Compute contact gaps
    contact_gaps = compute_contact_gaps(contacts)['all']
    gap_stats = compute_gap_statistics(contact_gaps)

    # Store the mean gap duration
    mean_gap_duration_list.append(gap_stats['mean_gap_duration_s'])

# Plot the mean number of contacts per day per satellite
plt.figure()
plt.plot(optimization_days, mean_contacts_per_day_per_sat_list, marker='o')
plt.xlabel(r'Simulation Window (Days)')
plt.ylabel(r'Mean Number of Contacts per Day per Satellite')
plt.grid()
plt.savefig('mean_contacts_per_day_per_satellite.png', dpi=1000)

# Plot the mean contact duration
plt.figure()
plt.plot(optimization_days, mean_contact_duration_list, marker='o')
plt.xlabel(r'Simulation Window (Days)')
plt.ylabel(r'Mean Contact Duration (s)')
plt.grid()
plt.savefig('mean_contact_duration.png', dpi=1000)

# Plot the mean gap duration
plt.figure()
plt.plot(optimization_days, mean_gap_duration_list, marker='o')
plt.xlabel(r'Simulation Window (Days)')
plt.ylabel(r'Mean Gap Duration (s)')
plt.grid()
plt.savefig('mean_gap_duration.png', dpi=1000)
