import matplotlib.pyplot as plt
import numpy as np

import constants


class Vizualizer:

    def __init__(self, sim_length) -> None:
        self.sim_length = sim_length

    def plot_results_reference_and_total_load(self, reference_load : np.ndarray, total_load : np.ndarray):
        """
        Creates two plots:
        - The total load of the neighborhood over time, compared with a reference
        - The normalized daily profile of the neighborhood, compared with a reference

        Feel free to include more plots if you want
        """

        # Plot total calculated load and the reference load
        reference_load = reference_load[0:self.sim_length]
        plt.title("Total Load Neighborhood")
        plt.plot(reference_load, label="Reference")
        plt.plot(total_load, label="Simulation")
        plt.xlabel('PTU [-]')
        plt.ylabel('Kilowatt [kW]')
        plt.legend()
        plt.grid(True)
        plt.show()

        # Calculate average daily profile
        amount_of_time_steps_in_day = constants.AMOUNT_OF_TIME_STEPS_IN_DAY
        time_step_seconds = constants.TIME_STEP_SECONDS

        power_split = np.split(total_load, self.sim_length / amount_of_time_steps_in_day)
        reference_split = np.split(reference_load, self.sim_length / amount_of_time_steps_in_day)
        power_split = sum(power_split)
        reference_split = sum(reference_split)
        max_val = max(max(power_split),max(reference_split))
        power_split /= max_val
        reference_split /= max_val
    
        # Plot the average daily profiles
        plt.title("Normalized Daily Power Profile")
        plt.plot(np.arange(1, amount_of_time_steps_in_day + 1) * time_step_seconds / 3600, power_split, label = 'Simulation')
        plt.plot(np.arange(1, amount_of_time_steps_in_day + 1) * time_step_seconds / 3600, reference_split, label = "Reference")
        plt.xlabel('Hour [-]')
        plt.ylabel('Relative Power [-]')
        plt.legend()
        plt.grid(True)
        plt.show()

    def print_metrics_renewable_share_total_load(self, renewable_share : np.ndarray, total_load : np.ndarray):
        """
        Calculates 3 metrics:
        - Total energy exported to the grid
        - Total energy imported from the grid
        - Percentage of imported energy to be from renewables

        Feel free to include more metrics if you want
        - Percentage of total energy  from renewables
        """

        time_step_seconds = constants.TIME_STEP_SECONDS
        ren_share = renewable_share[0: self.sim_length]

        # Calculate metrics
        energy_export = abs(sum(total_load[total_load < 0] * time_step_seconds/ 3600))
        energy_import = sum(total_load[total_load>0] * time_step_seconds/ 3600)
        renewable_import = sum(total_load[total_load > 0] * ren_share[total_load > 0]) * time_step_seconds/ 3600
        renewable_percentage = renewable_import/energy_import * 100
        #total_renewable_percentage = (renewable_import + sum(pv_data) ) / sum(total_load) * 100

        print("METRICS:")
        print("---------------------------------------")
        print(f"Energy Exported: {energy_export} kWh")
        print(f"Energy Imported: {energy_import} kWh")
        print(f"Share Renewable Energy Imported: {renewable_percentage} %")
        #print(f"Total Share Renewable Energy: {total_renewable_percentage} %")