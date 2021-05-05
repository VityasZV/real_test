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
            if (experiment_name[0] != "weibull_threads"):
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
        matches = re.findall("\d* KBytes/sec\s+\d*\s+[0-9,\.]+\s+", filetext)

        with open(os.getcwd()+ f"/{output_filename}", mode='w') as csv_file:
            field_names = ["time", "bitrate", "cwnd"]
            writer = csv.DictWriter(csv_file, fieldnames=field_names)
            writer.writeheader()
            for i, el in enumerate(matches):
                bitrate_and_cwnd = re.findall("[0-9,\.]+", el) #first will be bitrate, last is cwnd
                if bitrate_and_cwnd[-1].find('.') != -1:
                    bitrate_and_cwnd[-1] = float(bitrate_and_cwnd[-1])*1000
                writer.writerow({'time': i, 'bitrate': bitrate_and_cwnd[0], 'cwnd': bitrate_and_cwnd[-1]})

    def saving_results_from_dmesg(self, experiment) -> None:
        input_filename = f"{self.input_directory}/{experiment}/experiment_{experiment}_dmesg.txt"
        output_filename = f"{self.output_directory}/{experiment}/{experiment}_dmesg_cwnd.csv"

        textfile = open(os.getcwd()+f"/{input_filename}", 'r')
        filetext = textfile.read()
        print(f"SIZE OF FILETEXT dmesg {len(filetext)}")
        textfile.close()
        matches = re.findall(".*\d\d:\d\d:\d\d.*UPDATE cwnd = \d*", filetext)
        matches = [{"time": re.findall("\d\d:\d\d:\d\d", el)[0], "cwnd": re.findall("\d+", re.findall("= \d+", el)[0])[0], "speed": "?"} for el in matches]
        speed_matches = re.findall(".*\d\d:\d\d:\d\d.*estimated speed = \d+", filetext)
        speed_matches = [{"time": re.findall("\d\d:\d\d:\d\d", el)[0], "cwnd": "?", "speed": re.findall("\d+", re.findall("= \d+", el)[0])[0]} for el in speed_matches]
        all_matches = matches + speed_matches
        all_matches = sorted(all_matches, key=lambda tcs: tcs['time'])
        with open(os.getcwd()+ f"/{output_filename}", mode='w') as csv_file:
            field_names = ["time", "CWND", "estimated_speed"]
            writer = csv.DictWriter(csv_file, fieldnames=field_names)
            writer.writeheader()
            last_speed = 0
            last_cwnd = 0
            for el in all_matches:
                last_speed = el['speed'] if el['speed'] != "?" else last_speed
                last_cwnd = el['cwnd'] if el['cwnd'] != "?" else last_cwnd
                last_time = el['time']
                writer.writerow({'time': last_time, 'CWND': last_cwnd, 'estimated_speed': last_speed})
            


try:
    experiment_handler = ExperimentHandler(input_directory="test_output", output_directory="test_output/csv_files")
    for experiment in experiment_handler.experiments:
        os.mkdir(os.getcwd()+f"/{experiment_handler.output_directory}/{experiment}")
        experiment_handler.saving_results_from_iperf(experiment)
        experiment_handler.saving_results_from_dmesg(experiment)
except Exception as e:
    print(f"Error while performing script: {e}")
