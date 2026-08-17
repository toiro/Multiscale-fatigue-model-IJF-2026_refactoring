import warnings
from dataclasses import dataclass

import numpy as np  # The NumPy library is used to process arrays

# Warning policy: keep legacy suppression until numerical-warning handling is reviewed.
warnings.filterwarnings("ignore", category=np.RankWarning)
warnings.filterwarnings("ignore", category=RuntimeWarning)

# ----------------------------------------------------------4. Creat Field value function ------------------------------------------------------
# -------------------------------------------------------------------------------------------------------------------------------------------


@dataclass
class FieldValuesInput:
    sigma_nom: object
    y_lim: float
    z_lim: float
    active_element_size: object
    thickness: float


class FieldValuesFunction:
    def __init__(self, field_input: FieldValuesInput, material_data, load_queue):
        self.field_input = field_input
        self.field_cache = material_data.abaqus_field_cache
        self.x_Present = None
        self.x_steps_number = None
        self.sigma_Present = None
        self.sigma_Present_number = None
        self.stress_active_ele = None
        self.FieldValues_ACTIVE = None
        self.AeYZ = None
        self.load_queue = load_queue

        # call fuctions
        self.x_Present_creator()
        self.sigma_Present_creator()
        self.FData_AE()
        self.FData_AEE()
        self.FData_AEP()
        self.FData_AE_sigma()

    @property
    def _sigma_nom_list(self):
        return self.field_cache.sigma_nom_list

    @property
    def _sigma_to_step(self):
        return self.field_cache.sigma_to_step

    @property
    def _total_field_interpolators(self):
        return self.field_cache.total_field_interpolators

    @property
    def _elastic_field_interpolators(self):
        return self.field_cache.elastic_field_interpolators

    @property
    def _plastic_field_interpolators(self):
        return self.field_cache.plastic_field_interpolators

    # -------------------------------------------------------------------------------------------------------------------------------------------
    def FieldValuesA(self, x, y, z):
        """Return total stress/strain field components for the configured load."""
        y = np.array(y)
        z = np.array(z)
        interpolators = self._total_field_interpolators
        s = self._sigma_to_step(self.field_input.sigma_nom[self.load_queue])
        s1 = int(np.floor(s))
        s2 = int(np.ceil(s))

        if s - s1 <= 0.01:
            result = [interpolators[k][s1](x, y, z) for k in range(6)]
        elif s2 - s <= 0.01:
            result = [interpolators[k][s2](x, y, z) for k in range(6)]
        else:
            result = [
                (s2 - s) * interpolators[k][s1](x, y, z)
                + (s - s1) * interpolators[k][s2](x, y, z)
                for k in range(6)
            ]

        return result

    # elastic or plastic only
    def FieldValuesAE(self, x, y, z):
        """Return elastic stress/strain field components for the configured load."""
        y = np.array(y)
        z = np.array(z)
        interpolators = self._elastic_field_interpolators
        s = self._sigma_to_step(self.field_input.sigma_nom[self.load_queue])
        s1 = int(np.floor(s))
        s2 = int(np.ceil(s))

        if s - s1 <= 0.01:
            result = [interpolators[k][s1](x, y, z) for k in range(6)]
        elif s2 - s <= 0.01:
            result = [interpolators[k][s2](x, y, z) for k in range(6)]
        else:
            result = [
                (s2 - s) * interpolators[k][s1](x, y, z)
                + (s - s1) * interpolators[k][s2](x, y, z)
                for k in range(6)
            ]
        return result

    def FieldValuesAP(self, x, y, z):
        """Return plastic stress/strain field components for the configured load."""
        y = np.array(y)
        z = np.array(z)
        interpolators = self._plastic_field_interpolators
        s = self._sigma_to_step(self.field_input.sigma_nom[self.load_queue])
        s1 = int(np.floor(s))
        s2 = int(np.ceil(s))

        if s - s1 <= 0.01:
            result = [interpolators[k][s1](x, y, z) for k in range(6)]
        elif s2 - s <= 0.01:
            result = [interpolators[k][s2](x, y, z) for k in range(6)]
        else:
            result = [
                (s2 - s) * interpolators[k][s1](x, y, z)
                + (s - s1) * interpolators[k][s2](x, y, z)
                for k in range(6)
            ]
        return result

    def total_field_from_abaqus_cache(self, x, y, z):
        """Return total field directly from the Abaqus cache for the current load."""
        return self.FieldValuesA(x, y, z)

    def elastic_field_from_abaqus_cache(self, x, y, z):
        """Return elastic field directly from the Abaqus cache for the current load."""
        return self.FieldValuesAE(x, y, z)

    def plastic_field_from_abaqus_cache(self, x, y, z):
        """Return plastic field directly from the Abaqus cache for the current load."""
        return self.FieldValuesAP(x, y, z)

    def sigma_Present_creator(self):
        precision = 2
        start = 0
        end = self._sigma_nom_list[-1]

        # Define the initial step size and growth factor
        initial_step = 5
        step_growth_factor = 1

        # Initialize an empty list to store data
        self.sigma_Present = []

        # Gradually increase the step size and generate data
        current_step = initial_step
        current_value = start

        while current_value < end:
            self.sigma_Present.append(round(current_value, precision))
            current_value += current_step
            current_step *= step_growth_factor

        self.sigma_Present = np.array(self.sigma_Present)
        self.sigma_Present_number = len(self.sigma_Present)

    def FData_AE_sigma(self):

        AeNumY = int(self.field_input.y_lim / self.field_input.active_element_size[0])
        AeNumZ = int(self.field_input.z_lim / self.field_input.active_element_size[1])
        self.AeYZ = np.array(
            [
                [
                    self.field_input.active_element_size[0] * (i - 0.5 if i > 0 else 0),
                    self.field_input.active_element_size[1] * (j - 0.5 if j > 0 else 0),
                ]
                for i in range(AeNumY + 1)
                for j in range(AeNumZ + 1)
            ]
        )

        stress_active_list = []
        for i in range(len(self.AeYZ)):
            y_val = self.AeYZ[i, 0]
            z_val = self.AeYZ[i, 1]
            stress_at_sigma = [
                self.FieldValuesAOpen(σ, 0, y_val, z_val) for σ in self.sigma_Present
            ]
            stress_active_list.append(stress_at_sigma)
        self.stress_active_ele_sigma = np.array(stress_active_list)

    def FieldValues_ACTIVE_x0(self, σ, y, z):

        location = None
        for i in range(len(self.AeYZ)):
            if self.AeYZ[i, 0] == y and self.AeYZ[i, 1] == z:
                location = i
                break

        result = [
            np.interp(
                σ, self.sigma_Present, self.stress_active_ele_sigma[location][:, k]
            )
            for k in range(6)
        ]
        return result

    def active_surface_total_field_by_nominal_stress(self, sigma_nom, y, z):
        """Return active-surface total field interpolated by nominal stress."""
        return self.FieldValues_ACTIVE_x0(sigma_nom, y, z)

    def FieldValuesAOpen(self, σ, x, y, z):
        AES = self._total_field_interpolators
        s = self._sigma_to_step(σ)
        s1 = int(np.floor(s))
        s2 = int(np.ceil(s))

        def compute_result(x_val):
            if s - s1 <= 0.01:

                return [AES[k][s1](x_val, y, z) for k in range(6)]
            elif s2 - s <= 0.01:

                return [AES[k][s2](x_val, y, z) for k in range(6)]
            else:

                return [
                    (s2 - s) * AES[k][s1](x_val, y, z)
                    + (s - s1) * AES[k][s2](x_val, y, z)
                    for k in range(6)
                ]

        result = compute_result(x)

        return result

    def total_field_at_nominal_stress_from_abaqus_cache(self, sigma_nom, x, y, z):
        """Return total field from the Abaqus cache for an arbitrary nominal stress."""
        return self.FieldValuesAOpen(sigma_nom, x, y, z)

    # generate x_Present for 1D interpolation
    def x_Present_creator(self):
        precision = 2
        start = 0
        end = self.field_input.thickness  # modify

        # Define the initial step size and growth factor
        initial_step = 0.01
        step_growth_factor = 1

        # Initialize an empty list to store data
        self.x_Present = []

        # Gradually increase the step size and generate data
        current_step = initial_step
        current_value = start

        while current_value < end:
            self.x_Present.append(round(current_value, precision))
            current_value += current_step
            current_step *= step_growth_factor

        self.x_Present = np.array(self.x_Present)
        self.x_Present_number = len(self.x_Present)

    # Definition of the function FDataPAE to calculate the stress and strain of each area element
    def FData_AE(self):

        AeNumY = int(self.field_input.y_lim / self.field_input.active_element_size[0])
        AeNumZ = int(self.field_input.z_lim / self.field_input.active_element_size[1])

        # Calculate the centre coordinates of each area element
        self.AeYZ = np.array(
            [
                [
                    self.field_input.active_element_size[0] * (i - 0.5 if i > 0 else 0),
                    self.field_input.active_element_size[1] * (j - 0.5 if j > 0 else 0),
                ]
                for i in range(
                    AeNumY + 1
                )  # Start from 0 to include points with y-coordinate as 0
                for j in range(AeNumZ + 1)
            ]
        )

        y_Present = [
            [self.AeYZ[i, 0] for _ in range(self.x_Present_number)]
            for i in range(len(self.AeYZ))
        ]
        z_Present = [
            [self.AeYZ[i, 1] for _ in range(self.x_Present_number)]
            for i in range(len(self.AeYZ))
        ]
        stress_active0 = [
            self.FieldValuesA(self.x_Present, y_Present[i], z_Present[i])
            for i in range(len(self.AeYZ))
        ]
        self.stress_active_ele = np.array(stress_active0)

    def FData_AEE(self):  # ELASTIC

        AeNumY = int(self.field_input.y_lim / self.field_input.active_element_size[0])
        AeNumZ = int(self.field_input.z_lim / self.field_input.active_element_size[1])

        # Calculate the centre coordinates of each area element
        self.AeYZ = np.array(
            [
                [
                    self.field_input.active_element_size[0] * (i - 0.5 if i > 0 else 0),
                    self.field_input.active_element_size[1] * (j - 0.5 if j > 0 else 0),
                ]
                for i in range(
                    AeNumY + 1
                )  # Start from 0 to include points with y-coordinate as 0
                for j in range(AeNumZ + 1)
            ]
        )

        y_Present = [
            [self.AeYZ[i, 0] for _ in range(self.x_Present_number)]
            for i in range(len(self.AeYZ))
        ]
        z_Present = [
            [self.AeYZ[i, 1] for _ in range(self.x_Present_number)]
            for i in range(len(self.AeYZ))
        ]
        stress_active0 = [
            self.FieldValuesAE(self.x_Present, y_Present[i], z_Present[i])
            for i in range(len(self.AeYZ))
        ]
        self.stress_active_ele_E = np.array(stress_active0)

    def FData_AEP(self):

        AeNumY = int(self.field_input.y_lim / self.field_input.active_element_size[0])
        AeNumZ = int(self.field_input.z_lim / self.field_input.active_element_size[1])

        # Calculate the centre coordinates of each area element
        self.AeYZ = np.array(
            [
                [
                    self.field_input.active_element_size[0] * (i - 0.5 if i > 0 else 0),
                    self.field_input.active_element_size[1] * (j - 0.5 if j > 0 else 0),
                ]
                for i in range(
                    AeNumY + 1
                )  # Start from 0 to include points with y-coordinate as 0
                for j in range(AeNumZ + 1)
            ]
        )

        y_Present = [
            [self.AeYZ[i, 0] for _ in range(self.x_Present_number)]
            for i in range(len(self.AeYZ))
        ]
        z_Present = [
            [self.AeYZ[i, 1] for _ in range(self.x_Present_number)]
            for i in range(len(self.AeYZ))
        ]
        stress_active0 = [
            self.FieldValuesAP(self.x_Present, y_Present[i], z_Present[i])
            for i in range(len(self.AeYZ))
        ]
        self.stress_active_ele_P = np.array(stress_active0)

    def FieldValues_ACTIVE_Numpy(self, x, y, z):
        for i in range(len(self.AeYZ)):
            if self.AeYZ[i, 0] == y and self.AeYZ[i, 1] == z:
                location = i
                break
        return [
            np.interp(x, self.x_Present, self.stress_active_ele[location][k])
            for k in range(6)
        ]

    def active_element_total_field_by_depth(self, x, y, z):
        """Return active-element total field interpolated along crack depth."""
        return self.FieldValues_ACTIVE_Numpy(x, y, z)

    def FieldValues_ACTIVE_NumpyE(self, x, y, z):
        for i in range(len(self.AeYZ)):
            if self.AeYZ[i, 0] == y and self.AeYZ[i, 1] == z:
                location = i
                break
        return [
            np.interp(x, self.x_Present, self.stress_active_ele_E[location][k])
            for k in range(6)
        ]

    def active_element_elastic_field_by_depth(self, x, y, z):
        """Return active-element elastic field interpolated along crack depth."""
        return self.FieldValues_ACTIVE_NumpyE(x, y, z)

    def FieldValues_ACTIVE_NumpyP(self, x, y, z):
        for i in range(len(self.AeYZ)):
            if self.AeYZ[i, 0] == y and self.AeYZ[i, 1] == z:
                location = i
                break
        return [
            np.interp(x, self.x_Present, self.stress_active_ele_P[location][k])
            for k in range(6)
        ]

    def active_element_plastic_field_by_depth(self, x, y, z):
        """Return active-element plastic field interpolated along crack depth."""
        return self.FieldValues_ACTIVE_NumpyP(x, y, z)
