from enum import Enum
import os.path
import pickle
from typing import List
import numpy as np

import constants
from ModelClasses import House

class StrategyOrder(Enum):
    INDIVIDUAL = 1
    HOUSEHOLD = 2
    NEIGHBORHOOD = 3

class Simulator:
    """
    This class does several things:
    - Builds the neighborhood to simulate (.initialize)
    - Loops over all the time steps in the simulation and executes the control strategies (.control_strategy, ...)
    - Plots the results (.plot_results)
    - Calculates some metrics (.print_metrics)
    
    Please don't touch the parts related to the first two functionalities!
    """
    
    def __init__(self, control_order, battery_strategy, hp_strategy, pv_strategy, ev_strategy, neighborhood_strategy, house_strategy):
        self.list_of_houses : List[House] = []
        self.ren_share : np.ndarray = np.array([])
        self.temperature_data : np.ndarray = np.array([])
        self.batt_strategy = battery_strategy
        self.hp_strategy = hp_strategy
        self.pv_strategy = pv_strategy
        self.ev_strategy = ev_strategy
        self.house_strategy = house_strategy
        self.neighborhood_strategy = neighborhood_strategy
        self.total_load : np.ndarray = np.array([])
        self.pv_generated : np.ndarray = np.array([])
        self.control_order : List[StrategyOrder] = control_order

    def set_min_max_ders(self, time_step : int):
        for house in self.list_of_houses:
            house.pv.set_min_max(time_step)
            house.ev.set_min_max(time_step)
            house.batt.set_min_max(time_step)
            house.hp.set_min_max(time_step)

    def initialize(self, sim_length : int, number_of_houses : int, path_to_pkl_data : str, path_to_reference_data : str):
        #Scenario Parameters
        np.random.seed(42) 
        self.total_load = np.zeros(sim_length)
        self.pv_generated = np.zeros(sim_length)
    
        #Load pre-configured data
        if os.path.isfile(path_to_pkl_data): 
            self.sim_length = sim_length
            f = open(path_to_pkl_data, 'rb')
            scenario_data = pickle.load(f)
            baseloads = scenario_data['baseloaddata']

            if number_of_houses > len(baseloads) or sim_length > baseloads[0].size:
                raise ValueError(f"number_of_houses <= {len(baseloads)} and sim_length <= {baseloads[0].size}")

            pv_data = scenario_data['irrdata']
            ev_data = scenario_data["ev_data"]
            hp_data = scenario_data['hp_data']
            temperature_data = hp_data["ambient_temp"][:, 0]
            ren_share = scenario_data['ren_share']
            #determine distribution of data
            distribution = np.arange(number_of_houses)
            np.random.shuffle(distribution)
        
            #create a list containing all the household data and parameters
            list_of_houses = []
            for nmb in range(number_of_houses):
                list_of_houses.append(House(sim_length=sim_length,
                                            id=nmb, 
                                            baseload=baseloads[distribution[nmb]], 
                                            pv_data=pv_data[distribution[nmb]], 
                                            ev_data=ev_data[distribution[nmb]], 
                                            hp_data=hp_data, 
                                            temperature_data=temperature_data,
                                            house_strategy=self.house_strategy,
                                            pv_strategy=self.pv_strategy,
                                            ev_strategy=self.ev_strategy,
                                            batt_strategy=self.batt_strategy,
                                            hp_strategy=self.hp_strategy))

            self.list_of_houses : List[House] = list_of_houses
            self.ren_share = ren_share
            self.temperature_data = temperature_data
            self.hps = [house.hp for house in self.list_of_houses]
            self.evs = [house.ev for house in self.list_of_houses]
            self.pvs = [house.pv for house in self.list_of_houses]
            self.batteries = [house.batt for house in self.list_of_houses]
            self.ev_data = ev_data
            self.base_loads = [house.base_data for house in self.list_of_houses]
        else:
            print(f"Path to pickle data is invalid {path_to_pkl_data}")

        if os.path.isfile(path_to_reference_data):
            self.reference_load = np.load(path_to_reference_data)
        else:
            print(f"Path to reference data is invalid {path_to_reference_data}")

    def individual_strategy(self, time_step : int):
        for house in self.list_of_houses:
            house.pv.simulate_individual_entity(time_step, self.temperature_data, self.ren_share)
            house.ev.simulate_individual_entity(time_step, self.temperature_data, self.ren_share)
            house.hp.simulate_individual_entity(time_step, self.temperature_data, self.ren_share)
            house.batt.simulate_individual_entity(time_step, self.temperature_data, self.ren_share)

    def household_strategy(self, time_step : int):
        for house in self.list_of_houses:
            house.simulate_individual_entity(time_step, self.temperature_data, self.ren_share)

    def group_strategy(self, time_step : int):
        self.neighborhood_strategy(time_step, self.temperature_data, self.ren_share, self.base_loads, self.pvs, self.evs, self.hps, self.batteries)

    def control_strategy(self, time_step : int):
        try:  # catch errors caused by operations, probably caused by wrong strategy order
            for control_strategy_order in self.control_order:
                if control_strategy_order == StrategyOrder.HOUSEHOLD:
                    self.household_strategy(time_step)
                if control_strategy_order == StrategyOrder.INDIVIDUAL:
                    self.individual_strategy(time_step)
                if control_strategy_order == StrategyOrder.NEIGHBORHOOD:
                    self.group_strategy(time_step)
        except TypeError as e:
            message = f"Type error encountered: {e}. If this error is caused by applying an operation on None, " \
                      f"this likely means that you did not apply the correct strategy order, and you tried to use " \
                      f"consumption values not defined earlier."
            raise TypeError(message)



    def response(self, time_step : int) -> float:
        total_load = 0
        pv_generated = 0
        for house in self.list_of_houses:
            house.ev.response(time_step)
            house.hp.response(time_step)
            house.batt.response(time_step)
            house_load = (house.base_data[time_step] + house.pv.consumption[time_step] + house.ev.consumption[time_step] + house.batt.consumption[time_step] + house.hp.consumption[time_step])
            total_load += house_load
            pv_generated += abs(house.pv.consumption[time_step])
        return total_load, pv_generated

    def do_time_step(self, time_step : int):
        self.set_min_max_ders(time_step)
        self.control_strategy(time_step)
        self.total_load[time_step],self.pv_generated[time_step] = self.response(time_step)

    def start_simulation(self):
        for time_step in range(0, self.sim_length):
            self.do_time_step(time_step)

            # print progress
            if time_step % int(self.sim_length // 100) == 0:
                print(f"Progress: {time_step / self.sim_length:.1%}")
