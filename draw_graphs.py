import mmap
import sys
import re
import os
import csv
import glob
from numpy import genfromtxt
import matplotlib.pyplot as plt

from save_exp_to_csv_file import ExperimentHandler

"""
Drawing graphs by received csv files
"""

class ExperimentDrawer(ExperimentHandler):
    def __init__(self, input_directory: str, output_directory: str):
        super().__init__(input_directory, output_directory)

    def saving_results_from_iperf(self, experiment) -> None:
        input_filename = f"{self.input_directory}/{experiment}/{experiment}_iperf.csv"
        output_filename_1 = f"{self.output_directory}/{experiment}/{experiment}_iperf_speed.png"
        output_filename_2 = f"{self.output_directory}/{experiment}/{experiment}_iperf_cwnd.png"
        needed_columns = [["time", "cwnd"], ["time", "bitrate"]]
        out_files = [output_filename_1, output_filename_2]
        columns_t = [(0, 2), (0,1)]
        for columns, out_file, title, c_t in zip(needed_columns, out_files, [f"{experiment}_iperf_cwnd", f"{experiment}_iperf_speed"], columns_t):
            data = genfromtxt(input_filename, delimiter=',', skip_header=1, usecols=c_t)
            plt.plot(data)
            plt.xlabel(columns[0])
            plt.ylabel(columns[1])
            plt.savefig(out_file, bbox_inches='tight')
            plt.clf()

    def saving_results_from_dmesg(self, experiment) -> None:
        input_filename = f"{self.input_directory}/{experiment}/{experiment}_dmesg_cwnd.csv"
        output_filename_1 = f"{self.output_directory}/{experiment}/{experiment}_dmesg_speed.png"
        output_filename_2 = f"{self.output_directory}/{experiment}/{experiment}_dmesg_cwnd.png"
        needed_columns = [["time", "CWND"],["time", "estimated_speed"]]
        out_files = [output_filename_1, output_filename_2]
        columns_t = [(0,1), (0,2)]
        for columns, out_file, title, c_t in zip(needed_columns, out_files, [f"{experiment}_dmesg_cwnd", f"{experiment}_dmesg_speed"], columns_t):
            data = genfromtxt(input_filename, delimiter=',', skip_header=1, usecols=c_t)
            plt.xlabel(columns[0])
            plt.ylabel(columns[1])
            plt.xlim(0,60)
            plt.ylim(0,2000)
            plt.title(title)
            plt.plot_date
            plt.savefig(out_file, bbox_inches='tight')
       
experiment_drawer = ExperimentDrawer(input_directory="test_output/csv_files", output_directory="test_output/graphs")
for experiment in experiment_drawer.experiments:
    os.mkdir(os.getcwd()+f"/{experiment_drawer.output_directory}/{experiment}")
    experiment_drawer.saving_results_from_iperf(experiment)
    experiment_drawer.saving_results_from_dmesg(experiment)
