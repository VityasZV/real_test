import mmap
import sys
import re
import os
import csv
import glob

"""
Parsing output of experiments and saving them to csv files
"""

class ExperimentHandler:
    def __init__(self, input_directory: str, output_directory: str):
        self.input_directory = input_directory
        self.output_directory = output_directory
        # get names of experiments
        dirlist = glob.glob(os.getcwd()+f"/{input_directory}/*")
        experiments = []
        for _dir in dirlist:
            experiment_name = re.findall("[a-zA-Z0-9_]*$", _dir)
            experiments.append(experiment_name[0])
        print(dirlist)
        print(experiments)
        print("T")
        self.experiments = experiments
        print("create output dir")
        try: 
            os.mkdir(os.getcwd()+f"/{output_directory}")
        except:
            print("dir already created")

    def saving_results_from_iperf(self, experiment) -> None:
        input_filename = f"{self.input_directory}/{experiment}/experiment_{experiment}_iperf.txt"
        output_filename = f"{self.output_directory}/{experiment}/{experiment}_iperf.csv"

        textfile = open(os.getcwd()+f"/{input_filename}", 'r')
        filetext = textfile.read()
        textfile.close()
        matches = re.findall("\d* KBytes/sec", filetext)

        with open(os.getcwd()+ f"/{output_filename}", mode='w') as csv_file:
            field_names = ["time", "bitrate"]
            writer = csv.DictWriter(csv_file, fieldnames=field_names)
            writer.writeheader()
            for i, el in enumerate(matches):
                writer.writerow({'time': i, 'bitrate': re.match("\d*",el).group(0)})

    def saving_results_from_dmesg(self, experiment) -> None:
        input_filename = f"{self.input_directory}/{experiment}/experiment_{experiment}_dmesg.txt"
        output_filename = f"{self.output_directory}/{experiment}/{experiment}_dmesg_cwnd.csv"

        textfile = open(os.getcwd()+f"/{input_filename}", 'r')
        filetext = textfile.read()
        textfile.close()
        matches = re.findall("\[ \d*\.\d*\] UPDATE cwnd = \d*", filetext)

        with open(os.getcwd()+ f"/{output_filename}", mode='w') as csv_file:
            field_names = ["time", "CWND"]
            writer = csv.DictWriter(csv_file, fieldnames=field_names)
            writer.writeheader()
            for el in matches:
                time = re.findall("\d+\.\d+", el)[0]
                cwnd = re.findall("\d+", re.findall("= \d+", el)[0])[0]
                writer.writerow({'time': time, 'CWND': cwnd})


try:
    experiment_handler = ExperimentHandler(input_directory="test_output", output_directory="test_output/csv_files")
    for experiment in experiment_handler.experiments:
        os.mkdir(os.getcwd()+f"/{experiment_handler.output_directory}/{experiment}")
        experiment_handler.saving_results_from_iperf(experiment)
        experiment_handler.saving_results_from_dmesg(experiment)
except Exception as e:
    print(f"Error while performing script: {e}")
