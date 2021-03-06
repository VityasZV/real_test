import mmap
import sys
import re
import os
import csv
import glob
from numpy import genfromtxt
from collections import defaultdict
import matplotlib.pyplot as plt
import matplotlib.pylab as r_plt

from save_exp_to_csv_file import ExperimentHandler

"""
Drawing graphs by received csv files
"""

class ExperimentDrawer(ExperimentHandler):
    def __init__(self, input_directory: str, output_directory: str):
        super().__init__(input_directory, output_directory)

    def saving_results_from_iperf(self, experiment) -> None:
        input_filename = f"{self.input_directory}/{experiment}/{experiment}_iperf.csv"
        output_filename_1 = f"{self.output_directory}/{experiment}/{experiment}_iperf_cwnd.png"
        output_filename_2 = f"{self.output_directory}/{experiment}/{experiment}_iperf_speed.png"
        needed_columns = [["time", "cwnd"], ["time", "bitrate"]]
        out_files = [output_filename_1, output_filename_2]
        columns_t = [(2), (1)]
        for columns, out_file, title, c_t in zip(needed_columns, out_files, [f"{experiment}_iperf_cwnd", f"{experiment}_iperf_speed"], columns_t):
            data = genfromtxt(input_filename, delimiter=',', skip_header=1, usecols=c_t)
            plt.plot(data)
            plt.xlabel(columns[0])
            plt.ylabel(columns[1])
            plt.savefig(out_file, bbox_inches='tight')
            plt.clf()
            # plt.close()

    def saving_results_from_dmesg(self, experiment) -> None:
        input_filename = f"{self.input_directory}/{experiment}/{experiment}_dmesg.csv"
        output_filename_1 = f"{self.output_directory}/{experiment}/{experiment}_dmesg_cwnd.png"
        output_filename_2 = f"{self.output_directory}/{experiment}/{experiment}_dmesg_speed.png"
        needed_columns = [["time", "CWND"],["time", "speed"]]
        out_files = [output_filename_1, output_filename_2]
        columns_t = [(1), (2)]
        print("drawing results from dmesg...")
        for columns, out_file, title, c_t in zip(needed_columns, out_files, [f"{experiment}_dmesg_cwnd", f"{experiment}_dmesg_speed"], columns_t):
            data = genfromtxt(input_filename, delimiter=',', skip_header=1, usecols=c_t)
            plt.plot(data)
            plt.xlabel(columns[0])
            plt.ylabel(columns[1])
            plt.title(title)
            plt.savefig(out_file, bbox_inches='tight')
            plt.clf()
            plt.close()
            break  #so we get only cwnd full
        print("finished!")


    def forecast_results_from_dmesg(self, experiment)->None:
        input_filename = f"{self.input_directory}/{experiment}/{experiment}_dmesg.csv"
        output_filename = f"{self.output_directory}/{experiment}/{experiment}_dmesg_forecast.png"
        needed_columns = [["time", "CWND", "SPEED", "FORECAST"]]
        out_files = [output_filename]
        columns_t = [(1),(2), (3)]
        labels = ["CWND", "SPEED", "FORECAST"]
        for columns, out_file, title in zip(needed_columns, out_files, [f"{experiment}_dmesg_forecast"]):
            f, ax = plt.subplots()
            for c_t, l in zip(columns_t, labels):
                data = genfromtxt(input_filename, delimiter=',', skip_header=1, usecols=c_t)
                ax.plot(data, label=l)
                ax.legend()
            plt.title(title)
            plt.savefig(out_file, bbox_inches='tight')
            plt.clf()
            plt.close()

    def draw_final_result(self)->None:
        input_filename = "test_output/result/preparing.csv"
        exp_result = {}
        tr = ["cubic", "bbr", "bic", "htcp", "highspeed", "illinoise"]
        traditional_exp = {}.fromkeys(tr, 0.0)
        trt = [e + "_t" for e in tr]
        with open(os.getcwd()+ f"/{input_filename}", mode='r') as csv_file:
            reader = csv.DictReader(csv_file)
            for line in reader:
                if line["experiment"] in trt:
                    traditional_exp[line["experiment"][0:-2]] = int(line["average_bitrate"])
                else:
                    exp_result[line["experiment"]] = int(line["average_bitrate"])
        exp_series = {}
        tr_exp_series = {}
        for tr_name, tr_res in traditional_exp.items():
            tr_exp_series[tr_name] = {}
            for i in range(1, 128):
                tr_exp_series[tr_name][i] = tr_res
        print(len(exp_result.keys()))
        for e_name, e_res in exp_result.items():
            name = e_name[0:e_name.find("_e_")]
            number = int(re.findall("\d+", re.findall("_e_\d+", e_name)[0])[0])
            if name in exp_series.keys():
                exp_series[name][number]= int(e_res)
            else:
                exp_series[name] = {number: int(e_res)}
        print(exp_series.keys())
        for e_s_name, e_s_stuff in exp_series.items():
            f, ax = plt.subplots()
            print(f"drawing series of {e_s_name}")
            lists = sorted(e_s_stuff.items())
            x, y = zip(*lists)
            ax.plot(x,y,label=e_s_name)
            ax.legend()
            for t_name, t_stuff in tr_exp_series.items():
                lists = sorted(t_stuff.items())
                x, y = zip(*lists)
                ax.plot(x,y,label=t_name)
                ax.legend()
            plt.xlabel("exp_number")
            plt.ylabel("average_speed")
            plt.savefig(f"test_output/result/{e_s_name}.png", bbox_inches='tight')
            plt.clf()
            plt.close()

            


if __name__ == '__main__':      
    experiment_drawer = ExperimentDrawer(input_directory="test_output/csv_files", output_directory="test_output/graphs")
    for experiment in experiment_drawer.experiments:
        os.mkdir(os.getcwd()+f"/{experiment_drawer.output_directory}/{experiment}")
        experiment_drawer.saving_results_from_iperf(experiment)
        experiment_drawer.saving_results_from_dmesg(experiment)
        experiment_drawer.forecast_results_from_dmesg(experiment)
    experiment_drawer.draw_final_result()
    print("Drawing finished!")

