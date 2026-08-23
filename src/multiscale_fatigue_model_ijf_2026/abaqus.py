import datetime  # The datetime library is used to record the time of execution
import pickle  # The pickle library is used to save and read data in pkl format
import warnings
from dataclasses import dataclass
from pathlib import Path

import numpy as np  # The NumPy library is used to process arrays
from scipy import interpolate  # The scipy library is used to perform interpolation
from scipy.interpolate import (
    LinearNDInterpolator,
    griddata,
)  # The scipy library is used to perform interpolation  # The scipy library is used to perform interpolation

from .parameters import NominalStressExtractionMode
from .paths import (
    abaqus_dat_filename,
    abaqus_inp_filename,
    field_values_filename,
    resolve_cache_path,
    resolve_input_path,
)

# Warning policy: keep legacy suppression until numerical-warning handling is reviewed.
warnings.filterwarnings("ignore", category=np.RankWarning)
warnings.filterwarnings("ignore", category=RuntimeWarning)

# ----------------------------------------------------------2. ABAQUS data import ---------------------------------------------------------------
# -------------------------------------------------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class AbaqusImportInput:
    model_name: str
    steel: str
    specimen_type: str
    nominal_stress_extraction_mode: NominalStressExtractionMode
    width: float
    thickness: float


class AbaqusDatabaseCreator:
    def __init__(self, abaqus_input: AbaqusImportInput, base_dir=None, cache_dir=None):
        self.input = abaqus_input
        self.base_dir = Path(base_dir or ".")
        self.cache_dir = Path(cache_dir or self.base_dir)

        # Reading .inp files.
        self.inp_data = open(
            resolve_input_path(
                self.base_dir, abaqus_inp_filename(model_name=self.input.model_name)
            ),
            encoding="iso-8859-1",
        ).readlines()  # Read the .inp file and save it as a list of strings.
        # Reading .dat files.
        self.dat_data = open(
            resolve_input_path(
                self.base_dir, abaqus_dat_filename(model_name=self.input.model_name)
            ),
            encoding="iso-8859-1",
        ).readlines()  # Read the .dat file and save it as a list of strings.

        # Reading of material constants
        self.E = None  # Young's modulus
        self.ν = None  # Poisson's ratio
        self.AA = None  # Parameters used in crack and grain boundary interaction theory

        # Reading model information
        self.node0 = None
        self.node = None
        self.elements = None
        self.surface = None
        self.xyz = None
        self.nnm = None
        self.triming = None
        self.step = None
        self.sigma_nom_list = None
        self.f_sigma = None
        self.DataEES = None
        self.DataPES = None
        self.DataAES = None
        self.FDataE = None
        self.FDataP = None
        self.FDataA = None
        self.EES = None
        self.PES = None
        self.AES = None

        # call fuctions
        self.read_material_paramas()
        self.read_inp()
        self.read_dat()

    # ------------------------------------------------------------------------------------------------------------------
    # Material parameters
    def read_material_paramas(self):
        elastic = [i for i, line in enumerate(self.inp_data) if "*Elastic" in line][0]
        values_line = self.inp_data[elastic + 1].split(",")
        self.E, self.ν = map(float, values_line)
        self.AA = self.E / (4 * np.pi * (1 - self.ν**2))

    # Model information
    def read_inp(self):
        # ----------------------------------------------sub_function_START------------------------------------------------
        def move_instance(
            inst, xyz0
        ):  # Definition of the function for transforming the coordinates of nodes.
            tr = np.array(inst[0][:3])
            xyz1 = xyz0 + tr
            a0 = np.array(inst[1][:3])
            a1 = np.array(inst[1][3:6])
            axis = (a1 - a0) / np.linalg.norm(a1 - a0)
            phi = np.pi * inst[1][-1] / 180

            def rformula(xyz):
                r = xyz - a0
                return (
                    r * np.cos(phi)
                    + axis * (np.dot(axis, r)) * (1 - np.cos(phi))
                    + np.cross(axis, r) * np.sin(phi)
                )

            xyz2 = [list(map(rformula, xyz1))]
            return xyz2 + a0

        def x0(y, z):
            if y > y_max:
                return np.array([x_min_filter])
            else:
                interpolated_value = griddata(points, x, (y, z), method="linear")
                return interpolated_value

        def active_zone_element(n):  # Define the function to extract the area elements
            a_start = [
                idx
                for idx, line in enumerate(self.inp_data)
                if "elset=_ActiveZone_S" + str(n + 1) in line
            ][0] + 1
            inp_a_start0 = list(self.inp_data[a_start].split(","))
            inp_a_start1 = [int(item) for item in inp_a_start0]

            if self.inp_data[a_start - 1].split(",")[-1] == " generate\n":
                ae = list(range(inp_a_start1[0], inp_a_start1[1] + 1, inp_a_start1[2]))
                print("ae", ae)

            else:
                a_end_index = l_symbol.index(a_start - 1) + 1
                a_end = l_symbol[a_end_index] - 1
                print("000")
                print("a_start", a_start, "a_end", a_end)
                ae_lines = self.inp_data[a_start : a_end + 1]
                ae_lines = [line.strip() for line in ae_lines]
                ae0 = [list(map(int, line.split(",")[0:16])) for line in ae_lines]
                ae = [item for sublist in ae0 for item in sublist]

            selected_elements_ActiveZone = [
                sublist
                for index, sublist in enumerate(self.elements)
                if index + 1 in ae
            ]
            ActiveZone_n0 = [
                [sublist[i] for i in surface[n]]
                for sublist in selected_elements_ActiveZone
            ]
            return [item for sublist in ActiveZone_n0 for item in sublist]

        # ----------------------------------------------sub_function_END------------------------------------------------

        l_node = [i for i, line in enumerate(self.inp_data) if "*Node" in line]
        l_node_set = [i for i, line in enumerate(self.inp_data) if "*Nset" in line]
        l_element = [i for i, line in enumerate(self.inp_data) if "*Element" in line]
        l_element_set = [i for i, line in enumerate(self.inp_data) if "*Elset" in line]
        l_instance = [i for i, line in enumerate(self.inp_data) if "*Instance" in line]
        l_surface = [i for i, line in enumerate(self.inp_data) if "*Surface" in line]
        l_symbol = sorted(
            set().union(
                l_node, l_node_set, l_element, l_element_set, l_instance, l_surface
            )
        )

        # node
        node_start = l_node[0] + 1
        node_end = l_element[0] - 1
        node_lines = self.inp_data[node_start : node_end + 1]
        self.node0 = np.array(
            [list(map(float, line.split(",")[1:4])) for line in node_lines]
        )

        # element
        element_start = l_element[0] + 1
        element_end = l_node_set[0] - 1
        element_lines = self.inp_data[element_start : element_end + 1]
        self.elements = np.array(
            [list(map(int, line.split(",")[1:9])) for line in element_lines]
        )

        # coordinate transformation
        instance_start_index = next(
            (
                i + 1
                for i, line in enumerate(self.inp_data)
                if "*Instance, name=Specimen, part=Specimen" in line
            ),
            None,
        )
        end_instance_index = next(
            (
                i
                for i in range(instance_start_index, len(self.inp_data))
                if "*End Instance" in self.inp_data[i]
            ),
            None,
        )
        instance_data_lines = [
            line.strip()
            for line in self.inp_data[instance_start_index:(end_instance_index)]
        ]
        instance = [list(map(float, line.split(","))) for line in instance_data_lines]
        instance.append(["*End Instance"])
        if instance[0] == ["*End Instance"]:
            instance = [[0, 0, 0], [1, 0, 0, 0, 0, 0, 0]]
        if instance[1] == ["*End Instance"]:
            instance = [instance[0], [1, 0, 0, 0, 0, 0, 0]]
        self.node = np.round(move_instance(instance, self.node0)[0], 4)

        # Definition of the nodal set Triming in the Active Zone
        eTrimStart = [
            i for i, item in enumerate(self.inp_data) if "elset=Trim" in item
        ][0] + 1
        if self.inp_data[eTrimStart - 1].split(",")[-1] == " generate\n":

            eTrim0 = list(
                range(
                    int(self.inp_data[eTrimStart].split(",")[0]),
                    int(self.inp_data[eTrimStart].split(",")[1]) + 1,
                    int(self.inp_data[eTrimStart].split(",")[2]),
                )
            )

            eTrim = [x - 1 for x in eTrim0]
        else:
            eTrimStart_index = l_symbol.index(eTrimStart - 1) + 1
            eTrimEnd = l_symbol[eTrimStart_index] - 1
            eTrim_lines = self.inp_data[eTrimStart : eTrimEnd + 1]
            eTrim00 = [list(map(int, line.split(",")[0:16])) for line in eTrim_lines]
            eTrim0 = [item for sublist in eTrim00 for item in sublist]
            eTrim = [x - 1 for x in eTrim0]
        # while eTrim[-1] == 0:
        #     eTrim.pop()
        Triming0 = (np.unique(self.elements[eTrim, :].flatten()) - 1).tolist()

        # Extract Z-coordinates of Active Zone
        surface = (
            np.array(
                [
                    [1, 2, 3, 4],
                    [5, 6, 7, 8],
                    [1, 2, 6, 5],
                    [2, 3, 7, 6],
                    [3, 4, 8, 7],
                    [4, 1, 5, 8],
                ]
            )
            - 1
        ).tolist()
        AN0 = []
        for n in range(6):
            if any(
                "elset=_ActiveZone_S" + str(n + 1) in item for item in self.inp_data
            ):
                AN0.append(active_zone_element(n))
            else:
                AN0.append([])
        AN = sorted(set(item - 1 for sublist in AN0 if sublist for item in sublist))

        # (Function defining the x-coordinate of the surface of the active zone as (y,z)*)
        selected_node = self.node[AN, :]
        x = selected_node[:, [0]]
        y = selected_node[:, [1]]
        z = selected_node[:, [2]]
        x_min_filter = np.min(x)
        y_max = np.max(y)

        points = np.column_stack((y, z))
        selected_node_Triming = self.node[Triming0, :]

        xyz0 = np.array(
            [
                [coord[0] - x0(coord[1], coord[2])[0], coord[1], coord[2]]
                for coord in selected_node_Triming
            ]
        )
        ymax = np.max(1.2 * selected_node[:, [1]].flatten())
        zmax = np.max(1.2 * selected_node[:, [2]].flatten())
        condition1 = (xyz0[:, 1] < ymax) & (xyz0[:, 2] < zmax)
        self.xyz = xyz0[condition1]
        self.nnm = len(self.xyz)
        self.triming = [
            idx for idx, point in enumerate(xyz0) if point[1] < ymax and point[2] < zmax
        ]

    # read abaqus datebase
    def read_dat(self):
        # -----------------------------------------------------------sub_function__START------------------------------------------------
        def σ_eqE(ee):  # Functions returning elastic components
            return np.dot(CCC(0.3), ee)

        def σ_eqP(pe):  # Functions returning plastic components
            return np.dot((CCC(0.45) + CCC(0.55)) / 2, pe)

        def CCC(nu_temp):  # Definition of the elastic matrix function CCC
            GG = self.E / (2 * (1 + nu_temp))
            G0 = ((1 - nu_temp) * self.E) / ((1 + nu_temp) * (1 - 2 * nu_temp))
            G1 = (nu_temp * self.E) / ((1 + nu_temp) * (1 - 2 * nu_temp))

            return np.array(
                [
                    [G0, G1, G1, 0.0, 0.0, 0.0],
                    [G1, G0, G1, 0.0, 0.0, 0.0],
                    [G1, G1, G0, 0.0, 0.0, 0.0],
                    [0.0, 0.0, 0.0, GG, 0.0, 0.0],
                    [0.0, 0.0, 0.0, 0.0, GG, 0.0],
                    [0.0, 0.0, 0.0, 0.0, 0.0, GG],
                ]
            )

        def MapThread(data1, data2):  # pair
            data11 = data1.tolist()
            data22 = data2
            return [list(pair) for pair in zip(data11, data22)]

        # ----------------------------------------------sub_function__END------------------------------------------------

        LocationMAXIMUM = [
            idx - 2 for idx, line in enumerate(self.dat_data) if "MAXIMUM" in line
        ]

        # Elastic strain tensor
        EE_start = [idx + 3 for idx, line in enumerate(self.dat_data) if "EE11" in line]
        EE_end1 = list(
            map(
                lambda x: np.heaviside(x, 0),
                list(map(lambda x: x - np.array(LocationMAXIMUM), EE_start)),
            )
        )
        EE_end2 = list(map(lambda x: int(np.sum(x)) + 1, EE_end1))
        EE_end = [
            sublist
            for index, sublist in enumerate(LocationMAXIMUM)
            if index + 1 in EE_end2
        ]

        DataEE0_line0 = [
            self.dat_data[start : end + 1] for start, end in zip(EE_start, EE_end)
        ]
        DataEE0 = np.array(
            list(
                map(
                    lambda line_i: [
                        list(map(float, line.split()[1:])) for line in line_i
                    ],
                    DataEE0_line0,
                )
            )
        )
        DataEE = list(map(lambda DataEE0_sub: DataEE0_sub[self.triming, :], DataEE0))
        DataEES0 = [list(map(σ_eqE, sublist)) for sublist in DataEE]

        # # Plastic strain tensor
        PE_start = [idx + 3 for idx, line in enumerate(self.dat_data) if "PE11" in line]
        PE_end1 = list(
            map(
                lambda x: np.heaviside(x, 0),
                list(map(lambda x: x - np.array(LocationMAXIMUM), PE_start)),
            )
        )
        PE_end2 = list(map(lambda x: int(np.sum(x)) + 1, PE_end1))
        PE_end = [
            sublist
            for index, sublist in enumerate(LocationMAXIMUM)
            if index + 1 in PE_end2
        ]

        DataPE0_line0 = [
            self.dat_data[start : end + 1] for start, end in zip(PE_start, PE_end)
        ]
        DataPE0 = np.array(
            list(
                map(
                    lambda line_i: [
                        list(map(float, line.split()[1:7])) for line in line_i
                    ],
                    DataPE0_line0,
                )
            )
        )
        DataPE = list(map(lambda DataPE0_sub: DataPE0_sub[self.triming, :], DataPE0))
        DataPES0 = [list(map(σ_eqP, sublist)) for sublist in DataPE]

        # Equivalent stress tensor
        DataS0 = [[0.0, 0.0, 0.0, 0.0, 0.0, 0.0] for _ in range(self.nnm)]

        self.DataEES = [DataS0] + DataEES0
        self.DataPES = [DataS0] + DataPES0
        self.DataAES = (np.array(self.DataEES) + np.array(self.DataPES)).tolist()

        xyzDE = list(
            map(lambda DataEES_sub: MapThread(self.xyz, DataEES_sub), self.DataEES)
        )
        xyzDP = list(
            map(lambda DataPES_sub: MapThread(self.xyz, DataPES_sub), self.DataPES)
        )
        xyzDA = list(
            map(lambda DataAES_sub: MapThread(self.xyz, DataAES_sub), self.DataAES)
        )
        self.step = len(xyzDE)

        sigma_nom_list0 = self._extract_nominal_stresses()

        self.sigma_nom_list = [0.0] + sigma_nom_list0[0 : self.step - 1]

        self.FDataE = [
            [
                [[xyzDE[i][j][0], xyzDE[i][j][1][k]] for j in range(self.nnm)]
                for i in range(self.step)
            ]
            for k in range(6)
        ]
        self.EES = [
            [
                LinearNDInterpolator(
                    [point[0] for point in self.FDataE[k][i]],
                    [point[1] for point in self.FDataE[k][i]],
                )
                for i in range(self.step)
            ]
            for k in range(6)
        ]

        self.FDataP = [
            [
                [[xyzDP[i][j][0], xyzDP[i][j][1][k]] for j in range(self.nnm)]
                for i in range(self.step)
            ]
            for k in range(6)
        ]
        self.PES = [
            [
                LinearNDInterpolator(
                    [point[0] for point in self.FDataP[k][i]],
                    [point[1] for point in self.FDataP[k][i]],
                )
                for i in range(self.step)
            ]
            for k in range(6)
        ]

        self.FDataA = [
            [
                [[xyzDA[i][j][0], xyzDA[i][j][1][k]] for j in range(self.nnm)]
                for i in range(self.step)
            ]
            for k in range(6)
        ]
        self.AES = [
            [
                LinearNDInterpolator(
                    [point[0] for point in self.FDataA[k][i]],
                    [point[1] for point in self.FDataA[k][i]],
                )
                for i in range(self.step)
            ]
            for k in range(6)
        ]

        step_values = np.arange(0, self.step)
        self.f_sigma = interpolate.interp1d(
            self.sigma_nom_list, step_values, kind="linear"
        )

        # Define the variables you want to save
        data_to_save = {
            "EE": self.E,
            "ν": self.ν,
            "AA": self.AA,
            "nnm": self.nnm,
            "step": self.step,
            "sigma_nom_list": self.sigma_nom_list,
            "f_sigma": self.f_sigma,
            # 'DataEES': self.DataEES,
            # 'DataPES': self.DataPES,
            # 'DataAES': self.DataAES,
            # 'FDataE': self.FDataE,
            # 'FDataP': self.FDataP,
            # 'FDataA': self.FDataA,
            "EES": self.EES,
            "PES": self.PES,
            "AES": self.AES,
        }

        # Specify the file name for saving
        pkl_file_name = resolve_cache_path(
            self.cache_dir,
            field_values_filename(
                steel=self.input.steel, specimen_type=self.input.specimen_type
            ),
        )

        # Save the data to a file
        with open(pkl_file_name, "wb") as file:
            pickle.dump(data_to_save, file)

        return print(
            "Complete Definition of FieldValues Function :", datetime.datetime.now()
        )

    def _extract_nominal_stresses(self):
        mode = self.input.nominal_stress_extraction_mode
        if mode == NominalStressExtractionMode.SMOOTH_DSLOAD:
            return self._extract_smooth_dsload_nominal_stresses()
        if mode == NominalStressExtractionMode.THREE_POINT_BENDING_RF1:
            return self._extract_three_point_bending_rf1_nominal_stresses()
        if mode == NominalStressExtractionMode.COMPACT_SPECIMEN_DSLOAD:
            return self._extract_compact_specimen_dsload_nominal_stresses()
        raise NotImplementedError(
            "Abaqus nominal stress extraction is not implemented for "
            f"mode={mode!r}. {self.input.model_name} uses "
            f"specimen_type={self.input.specimen_type}; add an explicit "
            "nominal-stress mapping before generating its FieldValues cache."
        )

    def _extract_smooth_dsload_nominal_stresses(self):
        load_lines = [
            index + 1 for index, row in enumerate(self.inp_data) if "*Dsload" in row
        ]
        sigma_app_edge = [
            float(self.inp_data[line].split(",")[2]) for line in load_lines
        ]
        return [
            (15 * 1.6) / (self.input.width * self.input.thickness) * sigma
            for sigma in sigma_app_edge
        ]

    def _extract_three_point_bending_rf1_nominal_stresses(self):
        rf1_lines0 = [
            idx + 4 for idx, line in enumerate(self.dat_data) if "RF1" in line
        ]
        rf1_lines = [
            sublist
            for index, sublist in enumerate(self.dat_data)
            if index + 1 in rf1_lines0
        ]
        load = [4 * float(line.split()[1]) for line in rf1_lines]
        sigma_nom_list = [
            ((50 * load0) / 4) / ((self.input.width * self.input.thickness**2) / 6)
            for load0 in load
        ]
        return sigma_nom_list

    def _extract_compact_specimen_dsload_nominal_stresses(self):
        load_lines0 = [
            idx + 2 for idx, line in enumerate(self.inp_data) if "*Dsload" in line
        ]
        load_lines = [
            sublist
            for index, sublist in enumerate(self.inp_data)
            if index + 1 in load_lines0
        ]
        sigma_app_edge = [-1 * float(line.split(",")[2]) for line in load_lines]
        return [
            (self.input.width * (self.input.thickness + 0.5))
            / (self.input.width * self.input.thickness)
            * sigma
            for sigma in sigma_app_edge
        ]
