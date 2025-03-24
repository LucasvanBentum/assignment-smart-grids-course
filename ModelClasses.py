from typing import List, Dict
import numpy as np
import constants

TIME_STEP_SECONDS = constants.TIME_STEP_SECONDS

class SimulationEntity:
    """
    General Base class for all simulated entities
    
    Do not change!
    """
    def __init__(self, id : int, strategy):
        self.id = id
        self.strategy = strategy

    def simulate_individual_entity(self, time_step : int, temperature_data : np.ndarray, renewable_share : np.ndarray):
        pass

class Asset(SimulationEntity):
    """
    Base class for all simulated assets

    Do not change!
    """
    def __init__(self, id : int, sim_length: int, strategy):
        super().__init__(id, strategy)
        self.min = 0
        self.max = 0
        self.consumption = np.full(sim_length, None, dtype=object) # np.zeros(sim_length)

    def response(self, time_step : int):
        pass

    def check_response(self, time_step : int):
        pass

    def set_min_max(self, time_step : int):
        pass

class House(SimulationEntity):
    """
    Stores the assets in the house and can execute the house strategy
    
    Do not change!
    """
    def __init__(self, id : int, sim_length: int, baseload : np.ndarray, pv_data : np.ndarray, ev_data : Dict,
                 hp_data : Dict, temperature_data : np.array, house_strategy, pv_strategy, ev_strategy, batt_strategy,
                 hp_strategy):

        super().__init__(id, house_strategy)
        #General House Parameters
        self.base_data = baseload # load base load data into house

        # Assets
        self.pv = PVInstallation(id, pv_data, sim_length, pv_strategy)
        self.ev = EVInstallation(id, ev_data, sim_length, ev_strategy)
        self.batt = Battery(id, sim_length, batt_strategy)
        self.hp = Heatpump(id, sim_length, hp_data, temperature_data, hp_strategy)

    def simulate_individual_entity(self, time_step : int, temperature_data : np.ndarray, renewable_share : np.ndarray):
        return self.strategy(time_step, temperature_data, renewable_share, self.base_data, self.pv, self.ev, self.batt, self.hp)

class PVInstallation(Asset):
    """
    You do not need to change this class, but you can use the .max_power for your pv strategy, and you can use the limit
    function for inspiration for your own strategy
    """

    def __init__(self, id : int, pv_data : np.ndarray, sim_length : int, pv_strategy):
        super().__init__(id, sim_length, pv_strategy)
        self.max_power = pv_data

    def simulate_individual_entity(self, time_step : int, temperature_data : np.ndarray, renewable_share : np.ndarray):
        return self.strategy(time_step, temperature_data, renewable_share, self)

    def response(self, time_step : int):
        # The PVInstallation does not need to update anything
        self.check_response()

    def check_response(self, time_step : int):
        if np.round(self.consumption[time_step], 4) > 0.0:
            raise ValueError(f"PV generation should be < 0")

        if np.round(self.consumption[time_step], 4) < self.max_power[time_step]:
            raise ValueError(f"PV generation should be lower than max power")

    
    def set_min_max(self, time_step : int):
        """
        - min: fully curtail the PV
        - max: no curtailment, generate the max power
        """

        self.min = 0.0
        self.max = self.max_power[time_step]

class EVInstallation(Asset):
    """
    You do not need to change this class, but you can use the data in this class for your own strategies. You can also
    use the limit function for inspiration for your own strategy
    """

    def __init__(self, id : int, ev_data : Dict, sim_length : int, ev_strategy):
        super().__init__(id, sim_length, ev_strategy)
        self.power_max = ev_data['charge_cap'] #kW
        self.size = ev_data['max_SoC']#kWh
        self.min_charge = ev_data['min_charge']
        self.energy = ev_data['start_SoC'] #energy in kWh in de battery, changes each timstep
        self.energy_history = np.zeros(sim_length) #array to store previous battery state of charge for analyzing later
        self.session = ev_data['EV_status'] #details of the location of the EV (-1 is not at home, other number indicates the session number)
        self.session_trip_energy = ev_data['Trip_Energy'] #energy required during session
        self.session_arrive = ev_data['T_arrival'] #arrival times of session
        self.session_leave = ev_data['T_leave'] #leave times of session

    def simulate_individual_entity(self, time_step : int, temperature_data : np.ndarray, renewable_share : np.ndarray):
        return self.strategy(time_step, temperature_data, renewable_share, self)
    
    def response(self, time_step : int):
        if time_step != 0: #skip first timestep because you will look back one timestep
            # if the vehicle left the house this timestep, substract the energy lost during driving from the battery
            if self.session[time_step] == -1 and self.session[time_step - 1] != -1: 
                self.energy -= self.session_trip_energy[int(self.session[time_step - 1])]
                if self.energy <= 0:
                    self.energy = 0

        self.energy_history[time_step] = self.energy # save EV SoC for later analysis
        self.energy += self.consumption[time_step] * TIME_STEP_SECONDS / 3600  # update the battery

        self.check_response(time_step)

    def check_response(self, time_step : int):
        if np.round(self.consumption[time_step], 4) < 0.0:
            raise ValueError(f"Consumption of EV should be above 0.0")

        if np.round(self.consumption[time_step], 4) > self.power_max:
            raise ValueError(f"Consumption of EV should be below power_max")

        if np.round(self.energy, 4) < 0.0:
            raise ValueError(f"Energy in EV {self.id} is below 0")

        if np.round(self.energy, 4) > self.size:
            raise ValueError(f"Energy in EV {self.id} is above size")

    def set_min_max(self, time_step : int):
        """
        - min: no charging
        - max: try to reach the max state of charge during the session. As fast as possible.
        """
        
        self.min = 0
        
        if self.session[time_step] == -1:  # vehicle not home, so max power is 0
            self.max = 0
        else:
            required_energy = self.size #always charge to 100% SoC
            energy_to_charge = max(0, required_energy - self.energy)  # in kWh
            power_to_charge = energy_to_charge / (TIME_STEP_SECONDS / 3600)  # power required to charge all energy this step in kW
            self.max = min(self.power_max, power_to_charge)


class Battery(Asset):
    """
    You do not need to change this class, but you can use the data in this class for your own strategies. You can also
    use the limit function for inspiration for your own strategy
    """
    
    def __init__(self, id : int, sim_length : int, batt_strategy):
        # Based on Tesla Powerwall
        # https://www.tesla.com/sites/default/files/pdfs/powerwall/Powerwall_2_AC_Datasheet_EN_NA.pdf
        super().__init__(id, sim_length, batt_strategy)
        self.power_max = 5 #kW
        self.size = 13.5 #kWh
        self.energy = 6.25 #energy in kWh in de battery at every moment in time
        self.energy_history = np.zeros(sim_length)

    def simulate_individual_entity(self, time_step : int, temperature_data : np.ndarray, renewable_share : np.ndarray):
        return self.strategy(time_step, temperature_data, renewable_share, self)
    
    def response(self, time_step : int):
        self.energy_history[time_step] = self.energy #save batt SoC for later analysis
        self.energy += self.consumption[time_step] * TIME_STEP_SECONDS / 3600 # update battery

    def check_response(self, time_step : int):
        if np.round(self.consumption[time_step], 4) < - self.power_max:
            raise ValueError(f"Discharging power should be greater than -power_max")

        if np.round(self.consumption[time_step], 4) > self.power_max:
            raise ValueError(f"Charging power should be smaller than power_max")

        if np.round(self.energy, 4) < 0.0:
            raise ValueError(f"Energy in EV {self.id} is below 0")

        if np.round(self.energy, 4) > self.size:
            raise ValueError(f"Energy in EV {self.id} is above size")


    def set_min_max(self, time_step : int):
        """
        - min: discharge as much as possible, either all energy in the battery, or max discharge power
        - max: charge as much as possible, either the remaining part in the battery, or max charge power
        """

        # Min Strategy (discharge, negative)
        power_to_charge = - self.energy / (TIME_STEP_SECONDS / 3600)  # power needed to empty the battery this time step
        self.min = max(power_to_charge, - self.power_max)

        # Max Strategy (charge, positive)
        power_to_charge = (self.size - self.energy) / (TIME_STEP_SECONDS / 3600)  # power needed to fill the battery this time step
        self.max = min(power_to_charge, self.power_max)

class Heatpump(Asset):
    """
    You do not need to change this class, but you can use the data in this class for your own strategies. You can also
    use the limit function for inspiration for your own strategy
    """

    def __init__(self, id: int, sim_length : int, hp_data : Dict, T_ambient : np.ndarray, hp_strategy):
        super().__init__(id, sim_length, hp_strategy)

        # Thermal Properties House, DO NOT TOUCH OR USE
        self.T_ambient = T_ambient
        self.temperatures = hp_data['temperatures']
        self.super_matrix = hp_data['super_matrix'][id]
        self.a = hp_data['alpha'][id]
        self.v_part = hp_data['v_part'][id]
        self.b_part = hp_data['b_part'][id]
        self.M = hp_data['M'][id]
        self.f_inter = hp_data['f_inter']
        self.K_inv = hp_data["K_inv"][id]
        self.heat_demand_house = np.zeros(sim_length)
        self.heat_capacity_water = 4182  # [J/kg.K]

        # Building properties, You can change and use this
        self.T_set = 20.0 + 273  # [K] set point temperature in the house
        self.T_min = 18.0 + 273  # [K] Min temperature in the house
        self.T_max = 21.0 + 273  # [K] Max temperature in the house
        self.nominal_power = 8000.0  # [W]       Nominal capacity of heat pump installation
        self.tank_mass = 120.0  # [kg]      Mass of buffer = Volume of buffer (Water)
        self.tank_T_min_limit = 25.0 + 273 # [K]   Min temperature in the buffer tank
        self.tank_T_max_limit = 75.0 + 273  # [K]   Max temperature in the buffer tank
        self.tank_T_set = 40.0 + 273  # [K]   Temperature setpoint in buffer tank
        self.tank_T_init = 40.0 + 273  # [K]   Initial temperature in buffer tank
        self.tank_T = self.tank_T_init # Parameter initialized with initial temperature but changes over time

    def cop(self, T_tank: float, T_out: float) -> float:
        """
        Calculates the Coefficient of Performance (ratio between supplied heat and the electrical power)
        Do not change
        """
        return 8.736555867367798 - 0.18997851 * (T_tank - T_out) + 0.00125921 * (T_tank - T_out) ** 2
    
    def simulate_individual_entity(self, time_step : int, temperature_data : np.ndarray, renewable_share : np.ndarray):
        return self.strategy(time_step, temperature_data, renewable_share, self)
    
    def response(self, time_step):
        """
        Updates the tank temperature and the house temperatures, assuming that the house gets heated to the level that
        is required to be stable at the set point temperature

        Heat based calculations are in SI units

        Do not change this function!
        """
        T_ambient = self.T_ambient[time_step]
        heat_to_tank = (self.consumption[time_step] * TIME_STEP_SECONDS) * self.cop(self.tank_T_set, T_ambient)
        heat_to_tank = heat_to_tank * 1000 # in W

        # Calculate the heat required by the house
        heat_demand_house = self.calculate_heat_demand_house(time_step, self.T_set)

        # Calculate the temperature in the tank after supplying the required heat to the house
        dT_tank = (heat_to_tank - heat_demand_house) / (self.tank_mass * self.heat_capacity_water)
        tank_T = self.tank_T + dT_tank
        if tank_T < self.tank_T_min_limit:  # if demand is too great, the demand will be 0 but the tank will heat up
            heat_to_house = 0.0
        else:
            heat_to_house = heat_demand_house

        # Update the tank temperature
        dT_tank = (heat_to_tank - heat_to_house) / (self.tank_mass * self.heat_capacity_water)
        self.tank_T = self.tank_T + dT_tank

        # Update the house temperature
        heat_power_to_house = heat_to_house/ TIME_STEP_SECONDS
        self._update_house_temperatures(time_step, heat_power_to_house)

        self.check_response(time_step)


    def check_response(self, time_step : int):
        house_temperature = self.temperatures[1]
        if np.round(house_temperature, 4) < self.T_min:
            raise ValueError(f"House temperature is smaller than T_min")

        if np.round(self.tank_T, 4) < self.tank_T_min_limit:
            raise ValueError(f"Tank temperature is smaller than tank_T_min_limit")

        if np.round(self.tank_T, 4) > self.tank_T_max_limit:
            print(np.round(self.tank_T, 4), self.tank_T_max_limit)
            raise ValueError(f"Tank temperature is greater than tank_T_max_limit")
    
    def set_min_max(self, time_step: int):
        """
        - min: consume power such that the house temperature is kept at the set point and such that the tank
        temperature does not reach below its min
        - max: consume power such that the house temperature is kept at the set point and such that the tank
        temperature does not reach above its max

        Calculations are in SI units
        """
        T_ambient = self.T_ambient[time_step]

        # Calculate the amount of heat needed to keep the house temperature constant
        heat_demand_house = self.calculate_heat_demand_house(time_step, self.T_set)

        # Calculate the tank temperature as a result of heating the house
        tank_T_difference_no_hp = heat_demand_house / (self.tank_mass * self.heat_capacity_water)
        tank_T_no_hp = self.tank_T - tank_T_difference_no_hp

        # Min strategy: try to heat the tank back to the min limit if necessary
        min_heat_to_tank = self.tank_mass * self.heat_capacity_water * (self.tank_T_min_limit - tank_T_no_hp)
        min_heat_to_tank = max(0.0, min_heat_to_tank)
        min_heat_power_to_tank = min(self.nominal_power, min_heat_to_tank / TIME_STEP_SECONDS)

        # Max strategy: try to heat the tank as much as possible in this time step
        max_heat_to_tank = self.tank_mass * self.heat_capacity_water * (self.tank_T_max_limit - tank_T_no_hp)
        max_heat_power_to_tank = min(self.nominal_power, max_heat_to_tank / TIME_STEP_SECONDS)

        # Convert the heating power to electrical power using the Coefficient of Performance
        min_power = min_heat_power_to_tank / self.cop(self.tank_T_set, T_ambient)
        max_power = max_heat_power_to_tank / self.cop(self.tank_T_set, T_ambient)

        self.min = min_power / 1000.0  # convert to kW
        self.max = max_power / 1000.0  # convert to kW

    def calculate_heat_demand_house(self, time_step: int, house_temperature: float) -> float:
        """
        Helper function
        Calculates the heat (in J) required to heat the house to house_temperature (in K)
        Do not change
        """
        v = np.matmul(self.super_matrix, self.temperatures) + self.v_part[time_step]
        heat_demand_house = max(0, ((house_temperature - v[1])/(self.M[1, 1] * self.f_inter[1] + self.M[1, 2] * self.f_inter[2])) * 900)
        return heat_demand_house

    def _update_house_temperatures(self, time_step: int, heat_power_to_house: float):
        """
        Helper function
        Do not change
        """
        q_inter = heat_power_to_house * self.f_inter
        b = np.matmul(self.K_inv, q_inter) + self.b_part[time_step]
        self.temperatures = np.matmul(self.super_matrix, self.temperatures - b) + self.a[time_step] * 900 + b