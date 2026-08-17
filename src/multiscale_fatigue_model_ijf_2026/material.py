from __future__ import annotations

import datetime  # The datetime library is used to record the time of execution
import json  # Use the built-in JSON-related functions in Mathematica to save the data in JSON format, and then use JSON libraries in Python to process the JSON data
import os  # The os library is used to set up the working directory
import pickle  # The pickle library is used to save and read data in pkl format
import re  # Define regular expression patterns
import warnings
from dataclasses import dataclass
from pathlib import Path

import numpy as np  # The NumPy library is used to process arrays
import pandas as pd  # Using the pandas library to read CSV files
from scipy import interpolate  # The scipy library is used to perform interpolation
from scipy.interpolate import (
    griddata,
    interp1d,
)  # The scipy library is used to perform interpolation  # The scipy library is used to perform interpolation

# Warning policy: keep legacy suppression until numerical-warning handling is reviewed.
warnings.filterwarnings("ignore", category=np.RankWarning)
warnings.filterwarnings("ignore", category=RuntimeWarning)
from scipy.interpolate import RBFInterpolator

from .microstructure import MicrostructureGeneratedData, generate_particle_data
from .paths import (
    field_values_filename,
    first_grain_angle_filename,
    first_grain_aspect_filename,
    first_grain_size_filename,
    friction_strength_filename,
    grain_data_filename,
    monotonic_tensile_filename,
    resolve_cache_path,
    resolve_input_path,
    second_grain_thickness_prefix,
    weight_function_constants_filename,
)

# ----------------------------------------------------------3. Material data import --------------------------------------------------------------
# -------------------------------------------------------------------------------------------------------------------------------------------


GAUSS_WEIGHTS_10 = np.array(
    [
        0.06667134430869041,
        0.14945134915057556,
        0.21908636251598135,
        0.2692667193099942,
        0.2955242247147529,
        0.2955242247147529,
        0.26926671930999607,
        0.21908636251598135,
        0.1494513491505782,
        0.06667134430869041,
    ]
)

GAUSS_POINTS_10 = np.array(
    [
        -0.9739065285171692,
        -0.8650633666889868,
        -0.679409568299024,
        -0.4333953941292474,
        -0.14887433898163122,
        0.14887433898163122,
        0.43339539412924727,
        0.679409568299024,
        0.8650633666889848,
        0.9739065285171692,
    ]
)


@dataclass(frozen=True)
class MaterialImportInput:
    steel: str
    specimen_type: str
    thickness: float
    active_element_area: float
    first_grain: str
    second_grain: str


@dataclass(frozen=True)
class GrainDistributionData:
    """Measured grain-size, aspect-ratio, and angle distributions."""

    first_grain_df: np.ndarray
    first_grain_ids: np.ndarray
    first_grain_max: np.ndarray
    first_grain_aspect_df: np.ndarray
    first_grain_angle_df: np.ndarray
    first_grain_cdf: object
    first_grain_cdfr: object
    first_grain_aspect_cdfr: object
    first_grain_angle_cdf: object
    second_grain_df: np.ndarray | None
    second_grain_cdf: object | None
    second_grain_cdfr: object | None
    pearlite_rate: float | None
    average_grain_size: float
    maximum_grain_size: float
    grains_per_area_element: float


@dataclass(frozen=True)
class MechanicalPropertyData:
    """Measured monotonic tensile properties and phase friction strengths."""

    yield_strength: float | None
    tensile_strength: float | None
    reference_stress: float | None
    reduction_in_area: float | None
    ferrite_friction_strength: float | None
    pearlite_friction_strength: float | None


@dataclass(frozen=True)
class AbaqusFieldCacheData:
    """Cached Abaqus field data and interpolators used for stress lookup."""

    elastic_modulus: float | None
    poisson_ratio: float | None
    crack_interaction_constant: float | None
    node_count: int | None
    step_count: int | None
    sigma_nom_list: object
    sigma_to_step: object
    elastic_field_interpolators: object
    plastic_field_interpolators: object
    total_field_interpolators: object


@dataclass(frozen=True)
class WeightFunctionResources:
    """Weight-function and remote-stress interpolation resources."""

    secant_ellipse: object
    weight_function_constants: object
    weight_function_rbf: object
    weight_function_rbf_low: object
    weight_function_rbf_high: object
    gauss_weights_10: np.ndarray
    gauss_points_10: np.ndarray
    remote_stress_constants: object
    remote_stress_function: object
    qq_function: object


class MaterialDataImporter:
    """Load material resources and keep legacy attributes as compatibility views.

    Reading boundary:
    - measured input: grain CSV, monotonic tensile CSV, friction-strength CSV
    - cached numerical field: Abaqus FieldValues pickle
    - deterministic resources: weight-function and remote-stress interpolators
    - stochastic model data: generated or cached gData and derived model size

    Execution order:
    1. Load grain distributions from CSV.
    2. Load monotonic tensile/friction properties.
    3. Load Abaqus field cache.
    4. Build weight-function resources.
    5. Load or create generated microstructure data.
    6. Refresh typed views used by the refactored calculation layer.
    """

    def __init__(
        self, material_input: MaterialImportInput, base_dir=None, cache_dir=None
    ):
        self.input = material_input
        self.base_dir = Path(base_dir or ".")
        self.cache_dir = Path(cache_dir or self.base_dir)
        self.grain_distributions: GrainDistributionData | None = None
        self.mechanical_properties: MechanicalPropertyData | None = None
        self.abaqus_field_cache: AbaqusFieldCacheData | None = None
        self.weight_function_resources: WeightFunctionResources | None = None
        self.microstructure_data: MicrostructureGeneratedData | None = None

        self._load_grain_distributions()
        self._load_mechanical_properties()
        self._load_field_cache()
        self._build_weight_function_resources()
        self._build_microstructure_data()
        self._refresh_material_views()

    def _load_grain_distributions(self):
        """Load measured microstructure distributions from CSV input files."""

        self._second_grain_df: np.ndarray | None = None
        self._second_grain_cdf: object | None = None
        self._second_grain_cdfr: object | None = None
        self._pearlite_rate: float | None = None

        self._first_grain_df = pd.read_csv(
            self._input_path(
                first_grain_size_filename(
                    steel=self.input.steel,
                    first_grain=self.input.first_grain,
                )
            ),
            header=None,
        ).to_numpy()
        self._first_grain_ids = np.unique(self._first_grain_df[:, 0])
        self._first_grain_max = self._first_grain_df[-1]
        self._first_grain_aspect_df = pd.read_csv(
            self._input_path(
                first_grain_aspect_filename(
                    steel=self.input.steel,
                    first_grain=self.input.first_grain,
                )
            ),
            header=None,
        ).to_numpy()
        angle_file = self._input_path(
            first_grain_angle_filename(
                steel=self.input.steel, first_grain=self.input.first_grain
            )
        )
        if os.path.exists(angle_file):
            self._first_grain_angle_df = pd.read_csv(
                angle_file, header=None
            ).to_numpy()

        # Import perlite grain size from csv file
        if self.input.second_grain == "Pearlite":
            self._pearlite_thickness_files = [
                file
                for file in os.listdir(self.base_dir)
                if file.startswith(
                    second_grain_thickness_prefix(
                        steel=self.input.steel,
                        second_grain=self.input.second_grain,
                    )
                )
                and file.endswith(".csv")
            ]
            self._second_grain_df = pd.read_csv(
                self._input_path(self._pearlite_thickness_files[0]), header=None
            ).to_numpy()
            # distribution fraction
            self._second_grain_cdf = self._make_cdf(self._second_grain_df)
            self._second_grain_cdfr = self._make_cdfr(self._second_grain_df)
            self._pearlite_fraction()

        # distribution fraction
        self._first_grain_cdf = self._make_cdf(self._first_grain_df)
        self._first_grain_cdfr = self._make_cdfr(self._first_grain_df)
        self._first_grain_aspect_cdfr = self._make_cdfr_aspect(
            self._first_grain_aspect_df
        )
        self._first_grain_angle_cdf = self._make_cdf(self._first_grain_angle_df)

        # FirstGrain average and maximum grain size
        self._average_grain_size = sum(
            item[0] ** 3 * item[1] for item in self._first_grain_df
        ) / sum(
            item[0] ** 2 * item[1] for item in self._first_grain_df
        )
        self._maximum_grain_size = self._first_grain_cdf(1)
        self._grains_per_area_element = (4 * self.input.active_element_area) / (
            np.pi * self._average_grain_size**2
        )
        print("dave", self._average_grain_size)
        print("dmax", self._maximum_grain_size)

    def _load_mechanical_properties(self):
        self._load_monotonic_tensile_properties()
        self._load_friction_strength()

    def _load_field_cache(self):
        """Load the precomputed Abaqus field cache."""

        self._read_abaqus_field_cache()

    def _build_weight_function_resources(self):
        self._load_weight_function_constants()
        self._build_weight_function_interpolator()
        self._load_remote_stress_constants()

    def _build_microstructure_data(self):
        """Load or generate stochastic grain data used by the calculation."""

        self.microstructure_data = generate_particle_data(
            steel=self.input.steel,
            specimen_type=self.input.specimen_type,
            thickness=self.input.thickness,
            pearlite_rate=self._pearlite_rate,
            ferrite_friction_strength=self._ferrite_friction_strength,
            pearlite_friction_strength=self._pearlite_friction_strength,
            first_grain_cdf=self._first_grain_cdf,
            first_grain_cdfr=self._first_grain_cdfr,
            second_grain_cdf=self._second_grain_cdf,
            second_grain_cdfr=self._second_grain_cdfr,
            first_grain_aspect_cdfr=self._first_grain_aspect_cdfr,
            first_grain_angle_cdf=self._first_grain_angle_cdf,
            g_data_path=self._cache_path(
                grain_data_filename(
                    steel=self.input.steel, specimen_type=self.input.specimen_type
                )
            ),
        )
        self._generated_grain_data = self.microstructure_data.generated_grain_data
        self._pearlite_rate_normalized = (
            self.microstructure_data.pearlite_rate_normalized
        )
        self._grain_layers = self.microstructure_data.grain_layers
        self._grains_per_layer = self.microstructure_data.grains_per_layer

    def _refresh_material_views(self):
        self.grain_distributions = self._build_grain_distribution_view()
        self.mechanical_properties = self._build_mechanical_property_view()
        self.abaqus_field_cache = self._build_abaqus_field_cache_view()
        self.weight_function_resources = self._build_weight_function_view()
        self.microstructure_data = self._build_microstructure_view()

    def _build_grain_distribution_view(self):
        return GrainDistributionData(
            first_grain_df=self._first_grain_df,
            first_grain_ids=self._first_grain_ids,
            first_grain_max=self._first_grain_max,
            first_grain_aspect_df=self._first_grain_aspect_df,
            first_grain_angle_df=self._first_grain_angle_df,
            first_grain_cdf=self._first_grain_cdf,
            first_grain_cdfr=self._first_grain_cdfr,
            first_grain_aspect_cdfr=self._first_grain_aspect_cdfr,
            first_grain_angle_cdf=self._first_grain_angle_cdf,
            second_grain_df=getattr(self, "_second_grain_df", None),
            second_grain_cdf=getattr(self, "_second_grain_cdf", None),
            second_grain_cdfr=getattr(self, "_second_grain_cdfr", None),
            pearlite_rate=getattr(self, "_pearlite_rate", None),
            average_grain_size=self._average_grain_size,
            maximum_grain_size=self._maximum_grain_size,
            grains_per_area_element=self._grains_per_area_element,
        )

    def _build_mechanical_property_view(self):
        return MechanicalPropertyData(
            yield_strength=self._yield_strength,
            tensile_strength=self._tensile_strength,
            reference_stress=self._reference_stress,
            reduction_in_area=self._reduction_in_area,
            ferrite_friction_strength=self._ferrite_friction_strength,
            pearlite_friction_strength=self._pearlite_friction_strength,
        )

    def _build_abaqus_field_cache_view(self):
        return AbaqusFieldCacheData(
            elastic_modulus=self._elastic_modulus,
            poisson_ratio=self._poisson_ratio,
            crack_interaction_constant=self._crack_interaction_constant,
            node_count=self._node_count,
            step_count=self._step_count,
            sigma_nom_list=self._sigma_nom_list,
            sigma_to_step=self._sigma_to_step,
            elastic_field_interpolators=self._elastic_field_interpolators,
            plastic_field_interpolators=self._plastic_field_interpolators,
            total_field_interpolators=self._total_field_interpolators,
        )

    def _build_weight_function_view(self):
        return WeightFunctionResources(
            secant_ellipse=self._secant_ellipse,
            weight_function_constants=self._weight_function_constants,
            weight_function_rbf=getattr(self, "_weight_function_rbf", None),
            weight_function_rbf_low=self._weight_function_rbf_low,
            weight_function_rbf_high=self._weight_function_rbf_high,
            gauss_weights_10=GAUSS_WEIGHTS_10,
            gauss_points_10=GAUSS_POINTS_10,
            remote_stress_constants=self._remote_stress_constants,
            remote_stress_function=self._remote_stress_function,
            qq_function=self._qq,
        )

    def _build_microstructure_view(self):
        return MicrostructureGeneratedData(
            generated_grain_data=self._generated_grain_data,
            pearlite_rate_normalized=self._pearlite_rate_normalized,
            grain_layers=self._grain_layers,
            grains_per_layer=self._grains_per_layer,
        )

    # CDF function
    def _make_cdf(
        self, DF
    ):  #  Definition of the function makeCDF to calculate the cumulative distribution function of particle size
        CDF0 = np.cumsum(DF[:, 1])
        CDF = CDF0 * 0.99999 + np.arange(len(DF)) / len(DF) * 0.00001
        return interp1d(CDF, DF[:, 0], kind="linear", fill_value="extrapolate")

    def _make_cdfr(
        self, DF
    ):  #  Definition of the function makeCDF to calculate the cumulative distribution function of particle size
        CDF0 = np.cumsum(DF[:, 1])
        CDF = CDF0 * 0.99999 + np.arange(len(DF)) / len(DF) * 0.00001
        return interp1d(
            CDF,
            np.sqrt(np.pi) / 2.0 * DF[:, 0],
            kind="linear",
            fill_value="extrapolate",
        )

    def _make_cdfr_aspect(self, DF):
        CDF0 = np.cumsum(DF[:, 1])
        CDF = CDF0 * 0.99999 + np.arange(len(DF)) / len(DF) * 0.00001
        RA = np.sqrt(DF[:, 0])
        return interp1d(CDF, RA, kind="linear", fill_value="extrapolate")

    # Volume fraction of Pearlite
    def _pearlite_fraction(self):
        """Read the pearlite fraction proxy from the thickness CSV filename."""

        pattern = re.compile(r"(\d+\.\d+)")
        match = re.search(pattern, str(self._pearlite_thickness_files))
        if match:
            numeric_part = match.group(1)
            CRate = float(numeric_part)
        else:
            print("No numeric part found in the file name.")
        self._pearlite_rate = 1.5 * CRate

    # Monotonic tensile properties
    def _load_monotonic_tensile_properties(self):
        tensile_test_data = pd.read_csv(
            self._input_path(monotonic_tensile_filename(steel=self.input.steel))
        )
        (
            self._yield_strength,
            self._tensile_strength,
            self._reduction_in_area,
        ) = tensile_test_data.iloc[
            0, [0, 1, 2]
        ]
        self._reference_stress = 0.5 * (
            self._yield_strength + self._tensile_strength
        )

    # Friction strength of each phase
    def _load_friction_strength(self):
        friction_strength_data = pd.read_csv(
            self._input_path(friction_strength_filename(steel=self.input.steel))
        )
        self._pearlite_friction_strength: float | None = None
        if self.input.steel in ["H"]:
            self._ferrite_friction_strength = friction_strength_data.iloc[0, 0]
        else:
            (
                self._ferrite_friction_strength,
                self._pearlite_friction_strength,
            ) = friction_strength_data.iloc[0, [0, 1]]

    # Abaqus data
    def _read_abaqus_field_cache(self):
        """Read interpolators generated from Abaqus field values."""

        pkl_file_name = self._cache_path(
            field_values_filename(
                steel=self.input.steel, specimen_type=self.input.specimen_type
            )
        )
        with open(pkl_file_name, "rb") as file:
            data = pickle.load(file)

        variable_names = list(data.keys())
        print("  Stored variable names:", variable_names)

        # Access to specific variables
        self._elastic_modulus = data["EE"]
        self._poisson_ratio = data["ν"]
        self._crack_interaction_constant = data["AA"]
        self._node_count = data["nnm"]
        self._step_count = data["step"]
        self._sigma_nom_list = data["sigma_nom_list"]
        self._sigma_to_step = data["f_sigma"]
        self._elastic_field_interpolators = data["EES"]
        self._plastic_field_interpolators = data["PES"]
        self._total_field_interpolators = data["AES"]
        print(
            "Complete Reading ABAQUS FieldValues Function from pkl File :",
            datetime.datetime.now(),
        )

    # Weight function

    def _load_weight_function_constants(self):
        with open(self._input_path(weight_function_constants_filename())) as json_file1:
            Ellipse_WF_CF = json.load(json_file1)

        ldh = Ellipse_WF_CF["ldh"]
        WFCsmooth = Ellipse_WF_CF["WFCsmooth"]
        WFC3PBT = Ellipse_WF_CF["WFC3PBT"]
        WFCCS = Ellipse_WF_CF["WFCCS"]
        # Creating Interpolation Functions
        x_values = [item[0] for item in ldh]
        y_values = [item[1] for item in ldh]
        self._secant_ellipse = interpolate.interp1d(x_values, y_values)

        # Calculation of K-values via weight functions
        if self.input.specimen_type in ["Smooth"]:
            self._weight_function_constants = WFCsmooth
        elif self.input.specimen_type in ["R008", "R100"]:
            self._weight_function_constants = WFC3PBT
        elif self.input.specimen_type in ["CS", "CSS"]:
            self._weight_function_constants = WFCCS

    def _build_weight_function_interpolator(self):
        self._weight_function_rbf: object | None = None
        self._weight_function_rbf_low: object | None = None
        self._weight_function_rbf_high: object | None = None

        at_ac_values = [item[0] for item in self._weight_function_constants]
        values = [item[1] for item in self._weight_function_constants]

        at_values, ac_values = zip(*at_ac_values)
        at_values = np.array(at_values)
        ac_values = np.array(ac_values)
        values = np.array(values)

        if np.max(at_ac_values) > 0.8:
            mask_low = at_values <= 0.8
            mask_high = at_values >= 0.6

            if np.any(mask_low):
                self._weight_function_rbf_low = RBFInterpolator(
                    np.column_stack((at_values[mask_low], ac_values[mask_low])),
                    values[mask_low],
                    kernel="thin_plate_spline",
                    epsilon=1,
                )

            if np.any(mask_high):
                self._weight_function_rbf_high = RBFInterpolator(
                    np.column_stack((at_values[mask_high], ac_values[mask_high])),
                    values[mask_high],
                    kernel="thin_plate_spline",
                    epsilon=1,
                )
        else:
            self._weight_function_rbf = RBFInterpolator(
                np.column_stack((at_values, ac_values)),
                values,
                kernel="thin_plate_spline",
                epsilon=1,
            )

    def _qq(self, n):
        if n <= 1:
            return 1 + 1.464 * n**1.65
        else:
            return n**2 * (1 + 1.464 * (1 / n) ** 1.65)

    def _load_remote_stress_constants(self):
        with open(self._input_path(weight_function_constants_filename())) as json_file1:
            Ellipse_WF_CF = json.load(json_file1)
        # Extracting data for different variables
        CFsmooth = Ellipse_WF_CF["CFsmooth"]
        CF3PBT = Ellipse_WF_CF["CF3PBT"]
        CFCS = Ellipse_WF_CF["CFCS"]
        if self.input.specimen_type in ["Smooth"]:
            self._remote_stress_constants = CFsmooth
        elif self.input.specimen_type in ["R008", "R100"]:
            self._remote_stress_constants = CF3PBT
        elif self.input.specimen_type in ["CS", "CSS"]:
            self._remote_stress_constants = CFCS

        # Calculate CFlist2
        points = [(row[0], row[1]) for row in self._remote_stress_constants]
        values = [
            (row[2] * np.sqrt(self._qq(row[1])))
            / np.sqrt(row[0] * self.input.thickness)
            for row in self._remote_stress_constants
        ]
        self._remote_stress_function = lambda x, y: griddata(
            points, values, (x, y), method="cubic"
        )

    def _input_path(self, filename: str) -> Path:
        return resolve_input_path(self.base_dir, filename)

    def _cache_path(self, filename: str) -> Path:
        return resolve_cache_path(self.cache_dir, filename)


